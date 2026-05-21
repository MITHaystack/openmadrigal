C     $Id: testGeolib.f 7223 2020-09-10 19:43:50Z brideout $
C
      PROGRAM TGEOLIB
C
C     .. Local Scalars ..
      DOUBLE PRECISION ALT,AZM,ELM,F107,F107A,GDALT,GDLAT,GLAT,GLON,
     *                 GLONG,RANGE,SEC,SLATGC,SLATGD,SLON,SR,STL,TM
      INTEGER I,IYD,J,MASS
      LOGICAL QDIAG,QSPHERICAL
C     ..
C     .. Local Arrays ..
      DOUBLE PRECISION AP(7),D(9),RCOR(53),STCOR1(5),T(2)
      CHARACTER*7 TCOR(35)
C     ..
C     .. External Subroutines ..
      EXTERNAL COORD
C     ..
C     .. Data statements ..
      DATA TCOR/'     AZ','     EL','  RANGE','  GDLAT','   GLON',
     *     '  GDALT','      B','     BR','     BT','     BP','  RLATM',
     *     '  RLATI','     RL','   ALAT','   ALON','  GF(1)','  GF(2)',
     *     '  GF(3)','  GF(4)','CTAB(1)','CTAB(2)','CTAB(3)','CTAB(4)',
     *     'CTAB(5)','CTAB(6)','  COST1','  COST2','  COST3','   AINC',
     *     '    DEC','  GCLAT','  ASPCT',' CCGLAT',' CGDLAT','  CGLON'/
C     ..
C
      STCOR1(1) = 0.4261949921D+02
      STCOR1(2) = 0.2885079956D+03
      STCOR1(3) = 0.1460050046D+00
      STCOR1(4) = 0.4242779218D+02
      STCOR1(5) = 0.6368545333D+04
      QDIAG = .FALSE.
      QSPHERICAL = .FALSE.
      OPEN (UNIT=16,FILE='testGeolib.out')
      SLATGD = STCOR1(1)
      SLON = STCOR1(2)
      SR = STCOR1(5)
      WRITE (16,FMT='('' SLATGD = '', E13.5)') SLATGD
      WRITE (16,FMT='(''   SLON = '', E13.5)') SLON
      WRITE (16,FMT='(''     SR = '', E13.5)') SR
      SLATGC = STCOR1(4)
      TM = 1997.0D0
      TM = 0.19983D+04
      WRITE (16,FMT='(''     TM = '', E13.5)') TM
      AZM = -1.0D0
      ELM = -1.0D0
      RANGE = -1.0D0
      GDLAT = 50.0D0
      GLON = 290.0D0
      GDALT = 300.0D0
      DO 10 J = 1,32
         RCOR(J) = 0.0D0
   10 CONTINUE
      CALL COORD(SLATGD,SLON,SR,SLATGC,TM,AZM,ELM,RANGE,GDLAT,GLON,
     *           GDALT,QDIAG,QSPHERICAL,RCOR)
      DO 20 I = 1,35
         WRITE (16,FMT='(A7, '' = '', E13.5)') TCOR(I),RCOR(I)
   20 CONTINUE
C
      WRITE (16,FMT='(''GTD7 Output:'')')
      IYD = 98020
      SEC = 64876.0D0
      ALT = 90.0D0
      GLAT = 42.561D0
      GLONG = -71.491D0
      STL = 13.123D0
      F107A = 94.1D0
      F107 = 93.5D0
      DO 30 I = 1,7
         AP(I) = 3.0D0
   30 CONTINUE
      AP(1) = 15.0D0
      MASS = 4
      DO 40 I = 1,8
         D(I) = 0.0D0
   40 CONTINUE
      DO 50 I = 1,2
         T(I) = 0.0D0
   50 CONTINUE
C
      END
