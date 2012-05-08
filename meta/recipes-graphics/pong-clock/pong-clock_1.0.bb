DESCRIPTION = "A clock combined with a game of pong"
LICENSE = "GPLv2+"
DEPENDS = "virtual/libx11 xdmcp xau"

SRC_URI = "file://pong-clock-no-flicker.c"

LIC_FILES_CHKSUM = "file://pong-clock-no-flicker.c;startline=0;endline=23;md5=dd248d50f73f746d1ee78586b0b2ebd3"

S = "${WORKDIR}"

do_compile () {
	${CC} -o pong-clock pong-clock-no-flicker.c `pkg-config --cflags --libs x11 xau xdmcp`
}

do_install () {
	install -d ${D}${bindir}
	install -m 0755 pong-clock ${D}${bindir}
}
