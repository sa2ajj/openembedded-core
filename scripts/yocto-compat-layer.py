#!/usr/bin/env python3

# Yocto Project compatibility layer tool
#
# Copyright (C) 2017 Intel Corporation
# Released under the MIT license (see COPYING.MIT)

import os
import sys
import argparse
import logging
import time
import signal
import shutil
import collections

scripts_path = os.path.dirname(os.path.realpath(__file__))
lib_path = scripts_path + '/lib'
sys.path = sys.path + [lib_path]
import scriptutils
import scriptpath
scriptpath.add_oe_lib_path()
scriptpath.add_bitbake_lib_path()

from compatlayer import LayerType, detect_layers, add_layer, add_layer_dependencies, get_signatures
from oeqa.utils.commands import get_bb_vars

PROGNAME = 'yocto-compat-layer'
CASES_PATHS = [os.path.join(os.path.abspath(os.path.dirname(__file__)),
                'lib', 'compatlayer', 'cases')]
logger = scriptutils.logger_create(PROGNAME, stream=sys.stdout)

def test_layer_compatibility(td, layer, test_software_layer_signatures):
    from compatlayer.context import CompatLayerTestContext
    logger.info("Starting to analyze: %s" % layer['name'])
    logger.info("----------------------------------------------------------------------")

    tc = CompatLayerTestContext(td=td, logger=logger, layer=layer, test_software_layer_signatures=test_software_layer_signatures)
    tc.loadTests(CASES_PATHS)
    return tc.runTests()

def main():
    parser = argparse.ArgumentParser(
            description="Yocto Project compatibility layer tool",
            add_help=False)
    parser.add_argument('layers', metavar='LAYER_DIR', nargs='+',
            help='Layer to test compatibility with Yocto Project')
    parser.add_argument('-o', '--output-log',
            help='File to output log (optional)', action='store')
    parser.add_argument('--dependency', nargs="+",
            help='Layers to process for dependencies', action='store')
    parser.add_argument('--machines', nargs="+",
            help='List of MACHINEs to be used during testing', action='store')
    parser.add_argument('--additional-layers', nargs="+",
            help='List of additional layers to add during testing', action='store')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--with-software-layer-signature-check', action='store_true', dest='test_software_layer_signatures',
                       default=True,
                       help='check that software layers do not change signatures (on by default)')
    group.add_argument('--without-software-layer-signature-check', action='store_false', dest='test_software_layer_signatures',
                       help='disable signature checking for software layers')
    parser.add_argument('-n', '--no-auto', help='Disable auto layer discovery',
            action='store_true')
    parser.add_argument('-d', '--debug', help='Enable debug output',
            action='store_true')
    parser.add_argument('-q', '--quiet', help='Print only errors',
            action='store_true')

    parser.add_argument('-h', '--help', action='help',
            default=argparse.SUPPRESS,
            help='show this help message and exit')

    args = parser.parse_args()

    if args.output_log:
        fh = logging.FileHandler(args.output_log)
        fh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(fh)
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.ERROR)

    if not 'BUILDDIR' in os.environ:
        logger.error("You must source the environment before run this script.")
        logger.error("$ source oe-init-build-env")
        return 1
    builddir = os.environ['BUILDDIR']
    bblayersconf = os.path.join(builddir, 'conf', 'bblayers.conf')

    layers = detect_layers(args.layers, args.no_auto)
    if not layers:
        logger.error("Fail to detect layers")
        return 1
    if args.additional_layers:
        additional_layers = detect_layers(args.additional_layers, args.no_auto)
    else:
        additional_layers = []
    if args.dependency:
        dep_layers = detect_layers(args.dependency, args.no_auto)
        dep_layers = dep_layers + layers
    else:
        dep_layers = layers

    logger.info("Detected layers:")
    for layer in layers:
        if layer['type'] == LayerType.ERROR_BSP_DISTRO:
            logger.error("%s: Can't be DISTRO and BSP type at the same time."\
                     " The conf/distro and conf/machine folders was found."\
                     % layer['name'])
            layers.remove(layer)
        elif layer['type'] == LayerType.ERROR_NO_LAYER_CONF:
            logger.error("%s: Don't have conf/layer.conf file."\
                     % layer['name'])
            layers.remove(layer)
        else:
            logger.info("%s: %s, %s" % (layer['name'], layer['type'],
                layer['path']))
    if not layers:
        return 1

    shutil.copyfile(bblayersconf, bblayersconf + '.backup')
    def cleanup_bblayers(signum, frame):
        shutil.copyfile(bblayersconf + '.backup', bblayersconf)
        os.unlink(bblayersconf + '.backup')
    signal.signal(signal.SIGTERM, cleanup_bblayers)
    signal.signal(signal.SIGINT, cleanup_bblayers)

    td = {}
    results = collections.OrderedDict()
    results_status = collections.OrderedDict()

    layers_tested = 0
    for layer in layers:
        if layer['type'] == LayerType.ERROR_NO_LAYER_CONF or \
                layer['type'] == LayerType.ERROR_BSP_DISTRO:
            continue

        logger.info('')
        logger.info("Setting up for %s(%s), %s" % (layer['name'], layer['type'],
            layer['path']))

        shutil.copyfile(bblayersconf + '.backup', bblayersconf)

        missing_dependencies = not add_layer_dependencies(bblayersconf, layer, dep_layers, logger)
        if not missing_dependencies:
            for additional_layer in additional_layers:
                if not add_layer_dependencies(bblayersconf, additional_layer, dep_layers, logger):
                    missing_dependencies = True
                    break
        if not add_layer_dependencies(bblayersconf, layer, dep_layers, logger) or \
           any(map(lambda additional_layer: not add_layer_dependencies(bblayersconf, additional_layer, dep_layers, logger),
                   additional_layers)):
            logger.info('Skipping %s due to missing dependencies.' % layer['name'])
            results[layer['name']] = None
            results_status[layer['name']] = 'SKIPPED (Missing dependencies)'
            layers_tested = layers_tested + 1
            continue

        if any(map(lambda additional_layer: not add_layer(bblayersconf, additional_layer, dep_layers, logger),
                   additional_layers)):
            logger.info('Skipping %s due to missing additional layers.' % layer['name'])
            results[layer['name']] = None
            results_status[layer['name']] = 'SKIPPED (Missing additional layers)'
            layers_tested = layers_tested + 1
            continue

        logger.info('Getting initial bitbake variables ...')
        td['bbvars'] = get_bb_vars()
        logger.info('Getting initial signatures ...')
        td['builddir'] = builddir
        td['sigs'], td['tunetasks'] = get_signatures(td['builddir'])
        td['machines'] = args.machines

        if not add_layer(bblayersconf, layer, dep_layers, logger):
            logger.info('Skipping %s ???.' % layer['name'])
            results[layer['name']] = None
            results_status[layer['name']] = 'SKIPPED (Unknown)'
            layers_tested = layers_tested + 1
            continue

        result = test_layer_compatibility(td, layer, args.test_software_layer_signatures)
        results[layer['name']] = result
        results_status[layer['name']] = 'PASS' if results[layer['name']].wasSuccessful() else 'FAIL'
        layers_tested = layers_tested + 1

    ret = 0
    if layers_tested:
        logger.info('')
        logger.info('Summary of results:')
        logger.info('')
        for layer_name in results_status:
            logger.info('%s ... %s' % (layer_name, results_status[layer_name]))
            if not results[layer_name].wasSuccessful():
                ret = 2 # ret = 1 used for initialization errors

    cleanup_bblayers(None, None)

    return ret

if __name__ == '__main__':
    try:
        ret =  main()
    except Exception:
        ret = 1
        import traceback
        traceback.print_exc()
    sys.exit(ret)
