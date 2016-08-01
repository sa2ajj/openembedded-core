SUMMARY = "Extensible SDK toolchain meta-recipe"
DESCRIPTION = "Meta-recipe for ensuring the build directory contains all appropriate toolchain packages for using an IDE"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COREBASE}/LICENSE;md5=4d92cd373abda3937c2bc47fbc49d690 \
                    file://${COREBASE}/meta/COPYING.MIT;md5=3da9cfbcb788c80a0384361b4de20420"

DEPENDS = "virtual/libc gdb-cross-${TARGET_ARCH} qemu-native qemu-helper-native"

do_populate_sysroot[deptask] = "do_populate_sysroot"

# NOTE: There is logic specific to this recipe in setscene_depvalid()
# within sstate.bbclass, so if you copy or rename this and expect the same
# functionality you'll need to modify that as well.

LOCKED_SIGS_INDIR = "${D}/locked-sigs"

addtask do_locked_sigs after do_populate_sysroot
SSTATETASKS += "do_locked_sigs"
do_locked_sigs[sstate-inputdirs] = "${LOCKED_SIGS_INDIR}"
do_locked_sigs[sstate-outputdirs] = "${STAGING_DIR_HOST}/locked-sigs"

python do_locked_sigs() {
    import oe.copy_buildsystem
    outdir = os.path.join(d.getVar('LOCKED_SIGS_INDIR', True))
    bb.utils.mkdirhier(outdir)
    sigfile = os.path.join(outdir, 'locked-sigs-extsdk-toolchain.inc')
    oe.copy_buildsystem.generate_locked_sigs(sigfile, d)
}