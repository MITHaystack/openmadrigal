# $Id: Makefile.am 3304 2011-01-17 15:25:59Z brideout $
#
# Makefile.am for testF77 programs
#

AM_CFLAGS = -I../include

LDADD = -L../../madf/geolib -lgeo -L../madrec -lmadrec $(FLIBS)

# test programs only
check_PROGRAMS = tmaddataF77 tmadrecF77 tmaddata_nofile_F77

tmadrecF77_SOURCES = tmadrecF77.f

if IS_32BIT
tmaddataF77_SOURCES = tmaddataF77.f
else
tmaddataF77_SOURCES = tmaddataF77_64.f
endif

tmaddata_nofile_F77_SOURCES = tmaddata_nofile_F77.f


