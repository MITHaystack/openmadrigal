/******************************************************
*       madDeriveMethods
*
*  The madDeriveMethods module contains all logic used
*  in maddata to derive Madrigal parameters.  It is basically
*  a list of methods, all with the same signature:
*
*    int methodName(int inCount,
*                   double * inputArr,
*                   int outCount,
*                   double * outputArr,
*                   FILE * errFile)
*
*  Each method takes a list of Madrigal parameters as doubles,
*  and derives a list of Madrigal parameters as doubles.  Errors
*  are indicated by non-zero return codes, and messages can be
*  written to the errFile.
*
*  The order of these methods is defined in the CompiledExt
*  data structures called gCompExtList (global compiled extention
*  list).  This data structure tells the madDeriveEngine which
*  Madrigal parameters this method wants as inputs, and which it
*  produces as outputs. This global is defined in madDeriveEngine.c.
*
*  Note that the order of the methods as defined in gCompExtList
*  is significant.  The madDeriveEngine will use the first method
*  it finds that it can call successfully to derive a given
*  parameter; a later method that derives the same parameter will
*  be ignored.  Note also that those parameters derived by methods
*  before a given method in the list will be available to that method
*  as input parameters - methods are always called in the order they
*  appear in gCompExtList (if they are called at all).  For this reason,
*  the safest approach is to always add new methods to the end of the
*  list - this ensures that all previous derived parameters are
*  available to it.
*
*  The following are the steps required to extend the derived
*  methods in maddata:
*
*     1.  Add any new required parameters to parcods.tab.
*         Note that the parameter code 0 can always be assigned
*         unless you actually want to be save this new parameter
*         in a Cedar file
*
*     2.  Add two new lists of input and output parameters to the ones
*         already found at the beginning of madDeriveEngine.c.  If you
*         added new parameters in step 1, they will presumably
*         appear in the output list.  Use only inputs you absolutely
*         need - if any input is found to be missing, the engine
*         assumes your method will fail and will not call it.  Instead
*         it will set all output parameters to missing.  Use the naming
*         convention *In and *Out as in the following examples:
*
*             char *  getAzmIn[] = {"AZ1", "AZ2"};
*             char * getAzmOut[] = {"AZM"};
*
*     3.  Declare your method in this header file.  Remember,
*         it most have the form:
*                   int methodName(int inCount,
*                                  double * inputArr,
*                                  int outCount,
*                                  double * outputArr,
*                                  FILE * errFile)
*         If you are importing code from elsewhere, simply write a method with
*         the form above and call the real method from it.
*
*
*     4.  Add a line to the static const gCompExtList found in the
*         beginning of madDeriveEngine.c to register your method.  You'll
*         add the method name, the number of input parameters, the *In
*         array declared above, the number of output parameters, and the
*         *Out array declared above.  As discussed above, in most cases
*         you add to the end of the list.
*
*
*     5.  Implement the above method in madDeriveMethods.c.  If you need to import
*         from any other libraries to run your method, add that library and or source
*         to the Makefile.* in madc/madrec.
*
*     6.  Recompile madrec, test, and install.
*
* B. Rideout   12/2002        original
*
*  $Id: madDeriveMethods.h 7606 2023-09-18 17:20:27Z brideout $
*
*/

#ifndef _MAD_DERIVE_METHODS_
#define _MAD_DERIVE_METHODS_

#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <stdio.h>

#include <config.h>

#define PROTON_MASS 1.67261E-27


/* helper methods */

int checkErrorData(int inCount,
                   double * inputArr,
                   int outCount,
                   double * outputArr);

double getDebyeFactor(double Tr, double Pfac);

double getElecDensity(double Ti, double Tr, double Popl, double aspect);

int getTsyganenkoField(double time,
                       double gdlat,
                       double glon,
					   double gdalt,
					   double * swspd_array,
					   double imf_ygsm_now,
					   double * imf_zgsm_array,
					   double * swden_array,
					   double dst,
					   double * eq_xgsm,
					   double * eq_ygsm,
					   double * eq_xgse,
					   double * eq_ygse);

int traceTsyganenkoField(double time,
                         double gdlat,
						 double glon,
						 double gdalt,
						 double * swspd_array,
						 double imf_ygsm_now,
						 double * imf_zgsm_array,
						 double * swden_array,
						 double dst,
						 int    qualifier,
						 double stopAlt,
						 double * end_gdlat,
						 double * end_glon,
						 double * end_gdalt);

double getTsyganenkoWIndex(int index,
		                   double * swspd_array,
		                   double * imf_zgsm_array,
		                   double * swden_array);


int traceMagneticField(int year,
                       int month,
		       int day,
		       int hour,
		       int min,
		       int sec,
                       double gdlat,
		       double glon,
		       double gdalt,
		       int model,
		       int qualifier,
		       double stopAlt,
		       double * end_gdlat,
		       double * end_glon,
		       double * end_gdalt);
		       
int run_iri(int year,
            int month,
            int day,
            int hour,
            int min,
            int sec,
            double gdlat,
            double glon,
            double gdalt,
            double * iri);

int run_iri_3(int year,
              int month,
              int day,
              int hour,
              int min,
              int sec,
              double gdlat,
              double glon,
              double gdalt,
			  int * iap3,
			  double f107,
              double * iri);

/* initialize iri model - just called once */
void initialize_(void);

double faraday_rotation(int year, int month, int day, int hour, int min, int sec,
		                double sgdlat, double slon, double sgdalt,
		                double gdlat, double glon, double gdalt, double freq,
		                double * tec, double * total_tec);

double faraday_rotation_3(int year, int month, int day, int hour, int min, int sec,
		                  double sgdlat, double slon, double sgdalt,
		                  double gdlat, double glon, double gdalt,
						  int * iap3, double f107, double freq,
		                  double * tec, double * total_tec);

/* methods imported from geolib */

/* modified to let autotools handle name mangling issues */

#define COORD_F77 F77_FUNC (coord, COORD)

void COORD_F77(double * SLATGD,
               double * SLON,
               double * SR,
               double * SLATGC,
               double * TM,
               double * AZ,
               double * EL,
               double * RANGE,
               double * GDLAT,
               double * GLON,
               double * GDALT,
               int * QDIAG,
			   int * QSPHERICAL,
               double * RCOR);

#define COORDF_F77 F77_FUNC (coordf, COORD)

void COORDF_F77(double * SLATGD,
               double * SLON,
               double * SR,
               double * SLATGC,
               double * TM,
               double * AZ,
               double * EL,
               double * RANGE,
               double * GDLAT,
               double * GLON,
               double * GDALT,
               int * QDIAG,
			   int * QSPHERICAL,
               double * RCOR);

#define COORDFF_F77 F77_FUNC (coordff, COORD)

void COORDFF_F77(double * SLATGD,
               double * SLON,
               double * SR,
               double * SLATGC,
               double * TM,
               double * AZ,
               double * EL,
               double * RANGE,
               double * GDLAT,
               double * GLON,
               double * GDALT,
               int * QDIAG,
			   int * QSPHERICAL,
               double * RCOR);

#define POINT_F77 F77_FUNC (point, POINT)

void POINT_F77(double * SR,
               double * SLAT,
               double * SLON,
               double * AZ,
               double * EL,
               double * RANGE,
               double * PR,
               double * GLAT,
               double * GLON);

#define LOOK_F77 F77_FUNC (look, LOOK)

void LOOK_F77(double * SR,
              double * SLAT,
              double * SLON,
	      double * PR,
              double * GLAT,
              double * GLON,
              double * AZ,
              double * EL,
              double * RANGE);

#define TNF_F77 F77_FUNC (tnf, TNF)

double TNF_F77(double * ti,
               double * te,
	       double * ne,
	       double * php,
	       double * nol,
	       double * nhl,
	       double * nn4sl,
	       double * no2l,
	       double * nhel,
	       int * err);

#define CONVRT_F77 F77_FUNC (convrt, CONVRT)

void CONVRT_F77(int * imod,
                double * gdlat,
	        double * gdalt,
	        double * gclat,
	        double * rkm);

#define TS_RECALC_F77 F77_FUNC_ (ts_recalc_08, TS_RECALC_08)

void TS_RECALC_F77(int * iyear,
                   int * iday,
	           int * ihour,
	           int * min,
	           int * isec,
	           double * vx,
	           double * vy,
	           double * vz);


#define TS_SPHCAR_F77 F77_FUNC_ (ts_sphcar_08, TS_SPHCAR_08)

void TS_SPHCAR_F77(double * rkm,
                   double * gclat,
		   double * glon,
		   double * xgsm,
		   double * ygsm,
		   double * zgsm,
		   int * imod);

#define T04_S_F77 F77_FUNC_ (t04_s, T04_S)

void T04_S_F77(int * imod,
                double * parmod,
	        double * sdec,
	        double * xgsm,
	        double * ygsm,
	        double * zgsm,
	        double * bxgsm,
	        double * bygsm,
	        double * bzgsm);

#define BCARSP_F77 F77_FUNC (bcarsp_08, BCARSP_08)

void BCARSP_F77(double * x,
                double * y,
	        double * z,
	        double * bx,
	        double * by,
	        double * bz,
	        double * br,
	        double * btheta,
	        double * bpi);

#define GEOGSM_F77 F77_FUNC (geogsw, GEOGSW)

void GEOGSM_F77(double * xgeo,
                double * ygeo,
	        double * zgeo,
	        double * xgsm,
	        double * ygsm,
	        double * zgsm,
	        int *imod);

#define TRACE_F77 F77_FUNC (trace, TRACE)

void TRACE_F77(double * xgsm,
               double * ygsm,
	       double * zgsm,
	       double * dir,
	       double * dsmax,
	       double * err,
	       double * rlim,
	       double * ro,
	       int * imod,
	       double * parmod,
	       void (*t04_s_) (int *,double *,double *,double *,
	                        double *,double *,double *,
	                        double *,double *),
	       void (*igrf_gsm_) (double *,double *,double *,
	                          double *,double *,double *),
	       double * xf,
	       double * yf,
	       double * zf,
	       double * xx,
	       double * yy,
	       double * zz,
	       int * m,
	       int * lmax);

#define IGRF_GSM_F77 F77_FUNC_ (igrf_gsw_08, IGRF_GSW_08)

void IGRF_GSM_F77(double * XGSM,
                  double * YGSM,
	          double * ZGSM,
	          double * HXGSM,
	          double * HYGSM,
	          double * HZGSM);

#define GSMGSE_F77 F77_FUNC (gswgse, GSWGSE)

void GSMGSE_F77(double * XGSM,
                double * YGSM,
	        double * ZGSM,
	        double * XGSE,
	        double * YGSE,
	        double * ZGSE,
	        int * J);

#define CONVERT_GEO_COORD_F77 F77_FUNC_ (convert_geo_coord, CONVERT_GEO_COORD)

void CONVERT_GEO_COORD_F77(double * gclat,
                           double * glon,
			   double * rkm,
			   double * cglat,
			   double * cglon,
			   int * i_direction,
			   int * i_error);

#define LINTRA_F77 F77_FUNC (lintra, LINTRA)

void LINTRA_F77(double * TM,
                double * GCLAT,
	        double * GLON,
	        double * RKM,
	        double * ALT,
	        double * HALT,
	        double * PLAT,
	        double * PLON,
	        double * PRKM,
	        double * ARC,
	        double * ARAD,
	        double * ALAT,
	        double * ALON,
	        int * ISTOP,
	        int * NPR,
	        int * INIT,
	        int * IER);

#define ISRIM_F77 F77_FUNC (isrim, ISRIM)

void ISRIM_F77(int * KINST,
               double * DOY,
	       double * SLT,
	       double * ALT,
	       double * GLAT,
	       double * F107,
	       double * AP,
	       int * IPAR,
	       double * OUTPUT);

#define CONDUCT_F77 F77_FUNC (conduct, CONDUCT)

void CONDUCT_F77(double * NE,
                 double * NI,
	         double * N,
	         double * TE,
	         double * TI,
	         double * TN,
	         double * B,
	         double * XH,
	         double * XP);

#define IRI_SUB_F77 F77_FUNC_ (iri_sub, IRI_SUB)

void IRI_SUB_F77(unsigned int *JF,
                 int * JMAG,
                 float * ALATI,
                 float * ALONG,
                 int * year,
                 int * MMDD,
                 float * DHOUR,
                 float * HEIBEG,
                 float * HEIEND,
                 float * HEISTP,
                 float  OUTF[][20],
                 float  OARR[],
	         int * iap3,
	         float * f107);


#define GASPCT_F77 F77_FUNC (gaspct, GASPCT)

void GASPCT_F77(double * SLATGD,
                double * SLON,
	        double * SR,
	        double * SLATGC,
	        double * TM,
	        double * AZ,
	        double * EL,
	        double * RANGE,
	        double * GDLAT,
	        double * GLON,
	        double * GDALT,
	        double * B,
	        double * CASPCT,
	        double * ASPCT);

#define MLT_F77 F77_FUNC (mlt, MLT)

double MLT_F77(int * IYR,
		       int * T0,
		       double * MLONG,
		       double * MSLONG);


/* declare all derived parm methods here */


/* Pure time methods */


int getPrologTime(int inCount,
				  double * inputArr,
				  int outCount,
				  double * outputArr,
				  FILE * errFile);

int getByear(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getTime(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getBmd(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getBMonthDay(int inCount,
                 double * inputArr,
                 int outCount,
                 double * outputArr,
                 FILE * errFile);

int getMd(int inCount,
          double * inputArr,
          int outCount,
          double * outputArr,
          FILE * errFile);

int getUtUnix(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getDayno(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getBhm(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getBhhmmss(int inCount,
               double * inputArr,
               int outCount,
               double * outputArr,
               FILE * errFile);

int getEhhmmss(int inCount,
               double * inputArr,
               int outCount,
               double * outputArr,
               FILE * errFile);

int getHm(int inCount,
          double * inputArr,
          int outCount,
          double * outputArr,
          FILE * errFile);

int getUth(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getUts(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getBUth(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getInttms(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getInttmm(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getDatntd(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getUt(int inCount,
          double * inputArr,
          int outCount,
          double * outputArr,
          FILE * errFile);

int getBegUt(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getJdayno(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getJulian_date(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getJulian_day(int inCount,
                  double * inputArr,
                  int outCount,
                  double * outputArr,
                  FILE * errFile);

int getUt1(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getUt2(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getDut21(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getFyear(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

/* Space/time methods */

int getStation(int inCount,
               double * inputArr,
               int outCount,
               double * outputArr,
               FILE * errFile);

int getAltInc(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getAveAlt(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getAveDAlt(int inCount,
               double * inputArr,
               int outCount,
               double * outputArr,
               FILE * errFile);

int getResl(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getAzmDaz(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getDAzmDDaz(int inCount,
                double * inputArr,
                int outCount,
                double * outputArr,
                FILE * errFile);

int getElmDel(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getDElmDDel(int inCount,
                double * inputArr,
                int outCount,
                double * outputArr,
                FILE * errFile);

int getGeod(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getDGeod(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getGeodGdalt(int inCount,
                 double * inputArr,
                 int outCount,
                 double * outputArr,
                 FILE * errFile);

int getGeodAlt(int inCount,
               double * inputArr,
               int outCount,
               double * outputArr,
               FILE * errFile);

int getAzElRange(int inCount,
                 double * inputArr,
                 int outCount,
                 double * outputArr,
                 FILE * errFile);

int getSZen(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getSltmut(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getSlt(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getSdwHt(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getSuntime(int inCount,
               double * inputArr,
               int outCount,
               double * outputArr,
               FILE * errFile);

int getTecGdalt(int inCount,
                double * inputArr,
                int outCount,
                double * outputArr,
                FILE * errFile);

int getGcdist(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getMag(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getMag2(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getMagStat(int inCount,
               double * inputArr,
               int outCount,
               double * outputArr,
               FILE * errFile);

int getTsygan(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getAacgm(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int fromAacgm(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);


int getEregion(int inCount,
               double * inputArr,
               int outCount,
               double * outputArr,
               FILE * errFile);

int getAspect(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getSltc(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getAplt(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getSZenc(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getConjSun(int inCount,
               double * inputArr,
               int outCount,
               double * outputArr,
               FILE * errFile);

int getGeo(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getDst(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getFof2(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getPopl(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getPop(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getNeFromNe8(int inCount,
           	   double * inputArr,
			   int outCount,
			   double * outputArr,
			   FILE * errFile);

int getDNeFromDNe8(int inCount,
           	   double * inputArr,
			   int outCount,
			   double * outputArr,
			   FILE * errFile);


int getNel(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getNe(int inCount,
          double * inputArr,
          int outCount,
          double * outputArr,
          FILE * errFile);

int getDNel(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getDNe(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getNemaxl(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getNemax(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getTr(int inCount,
          double * inputArr,
          int outCount,
          double * outputArr,
          FILE * errFile);

int getTe(int inCount,
          double * inputArr,
          int outCount,
          double * outputArr,
          FILE * errFile);

int getTi(int inCount,
          double * inputArr,
          int outCount,
          double * outputArr,
          FILE * errFile);

int getDteCctitr(int inCount,
                 double * inputArr,
                 int outCount,
                 double * outputArr,
                 FILE * errFile);

int getDte(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getCol(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getCo(int inCount,
          double * inputArr,
          int outCount,
          double * outputArr,
          FILE * errFile);

int getNeNel(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getDNeDNel(int inCount,
               double * inputArr,
               int outCount,
               double * outputArr,
               FILE * errFile);

int getVisrNe(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getVisrTe(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getVisrTi(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getVisrVo(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getVisrHNMax(int inCount,
                 double * inputArr,
                 int outCount,
                 double * outputArr,
                 FILE * errFile);

int getVisrNeDiff(int inCount,
                  double * inputArr,
                  int outCount,
                  double * outputArr,
                  FILE * errFile);

int getVisrNelDiff(int inCount,
                   double * inputArr,
                   int outCount,
                   double * outputArr,
                   FILE * errFile);

int getVisrTeDiff(int inCount,
                  double * inputArr,
                  int outCount,
                  double * outputArr,
                  FILE * errFile);

int getVisrTiDiff(int inCount,
                  double * inputArr,
                  int outCount,
                  double * outputArr,
                  FILE * errFile);

int getVisrVoDiff(int inCount,
                  double * inputArr,
                  int outCount,
                  double * outputArr,
                  FILE * errFile);

int getSn(int inCount,
          double * inputArr,
          int outCount,
          double * outputArr,
          FILE * errFile);

int getSnp3(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getChip31(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getWchsq1(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getChisq1(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getChip32(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getWchsq2(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getChisq2(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getVi1Vi1f(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getVi2Vi2f(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getVipeVipe1(int inCount,
                 double * inputArr,
                 int outCount,
                 double * outputArr,
                 FILE * errFile);

int getVipeVipe2(int inCount,
                 double * inputArr,
                 int outCount,
                 double * outputArr,
                 FILE * errFile);

int getVipnVipn1(int inCount,
                 double * inputArr,
                 int outCount,
                 double * outputArr,
                 FILE * errFile);

int getVipnVipn2(int inCount,
                double * inputArr,
                int outCount,
                double * outputArr,
                FILE * errFile);

int getVi6Vipu(int inCount,
               double * inputArr,
               int outCount,
               double * outputArr,
               FILE * errFile);

int getViGeom(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getViGeod(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getVn1Vn1p2(int inCount,
                double * inputArr,
                int outCount,
                double * outputArr,
                FILE * errFile);

int getVn2Vn2p2(int inCount,
                double * inputArr,
                int outCount,
                double * outputArr,
                FILE * errFile);

int getVnGeom(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getVnGeod(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getEFGeom(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getEFGeod(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile);

int getJGeom(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getJGeod(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getTn(int inCount,
          double * inputArr,
	  int outCount,
	  double * outputArr,
	  FILE * errFile);

int getTnNoPhp(int inCount,
               double * inputArr,
	       int outCount,
	       double * outputArr,
	       FILE * errFile);

int getDTn(int inCount,
           double * inputArr,
	       int outCount,
	       double * outputArr,
	       FILE * errFile);

int getCond(int inCount,
            double * inputArr,
            int outCount,
            double * outputArr,
            FILE * errFile);

int getDCond(int inCount,
             double * inputArr,
             int outCount,
             double * outputArr,
             FILE * errFile);

int getImf(int inCount,
           double * inputArr,
           int outCount,
           double * outputArr,
           FILE * errFile);

int getIri (int inCount,
	    double * inputArr,
	    int OutCount,
	    double * outputArr,
	    FILE * errFile);

/* declaration of methods that use multiple rows */

int getTestAveAlt(int numRows,
                  int inCount,
                  double ** inputArr,
                  int outCount,
                  double ** outputArr,
                  FILE * errFile);

#endif

