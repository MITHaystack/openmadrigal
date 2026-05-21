/*
  See madDeriveEngine.h for overview of this module.

  $Id: madDeriveEngine.c 7605 2023-09-18 17:19:53Z brideout $

  Written 11/2002 by B. Rideout
*/



#include <madDeriveMethods.h>
#include <madDeriveEngine.h>
#include <string.h>
#include <assert.h>
#include <math.h>


/* declare all arrays of parameter mnemonics here                      */
/* Naming convention: end input array name "In" and output array "Out" */

/*  Pure time */
static const char * getPrologTimeIn[]     = {"UT1_UNIX", "UT2_UNIX"};
static const char * getPrologTimeOut[]    = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getByearIn[]          = {"IBYR"};
static const char * getByearOut[]         = {"BYEAR"};
static const char * getTimeIn[]           = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getTimeOut[]          = {"YEAR", "MONTH", "DAY", "HOUR", "MIN", "SEC", "CSEC"};
static const char * getBmdIn[]            = {"IBDT"};
static const char * getBmdOut[]           = {"BMD"};
static const char * getBMonthDayIn[]      = {"IBDT"};
static const char * getBMonthDayOut[]     = {"BMONTH","BDAY"};
static const char * getMdIn[]             = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getMdOut[]            = {"MD"};
static const char * getUtUnixIn[]         = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getUtUnixOut[]        = {"UT1_UNIX", "UT2_UNIX"};
static const char * getDaynoIn[]          = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getDaynoOut[]         = {"DAYNO"};
static const char * getBhmIn[]            = {"IBHM"};
static const char * getBhmOut[]           = {"BHM"};
static const char * getBhhmmssIn[]        = {"IBHM", "IBCS"};
static const char * getBhhmmssOut[]       = {"BHHMMSS"};
static const char * getEhhmmssIn[]        = {"IEHM", "IECS"};
static const char * getEhhmmssOut[]       = {"EHHMMSS"};
static const char * getHmIn[]             = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getHmOut[]            = {"HM"};
static const char * getUthIn[]            = {"FIRST_IBYR", "FIRST_IBDT", "FIRST_IBHM", "FIRST_IBCS",
                                             "IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getUthOut[]           = {"UTH"};
static const char * getUtsIn[]            = {"FIRST_IBYR", "FIRST_IBDT", "FIRST_IBHM", "FIRST_IBCS",
                                             "IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getUtsOut[]           = {"UTS"};
static const char * getBUthIn[]           = {"FIRST_IBYR", "FIRST_IBDT", "FIRST_IBHM", "FIRST_IBCS",
                                             "IBYR", "IBDT", "IBHM", "IBCS"};
static const char * getBUthOut[]          = {"B_UTH"};
static const char * getInttmsIn[]         = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getInttmsOut[]        = {"INTTMS"};
static const char * getInttmmIn[]         = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getInttmmOut[]        = {"INTTMM"};
static const char * getDatntdIn[]         = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getDatntdOut[]        = {"DATNTD"};
static const char * getUtIn[]             = {"UTH"};
static const char * getUtOut[]            = {"UT"};
static const char * getBegUtIn[]          = {"B_UTH"};
static const char * getBegUtOut[]         = {"BEG_UT"};
static const char * getJdaynoIn[]         = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getJdaynoOut[]        = {"JDAYNO"};
static const char * getJulian_dateIn[]    = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS", "JDAYNO"};
static const char * getJulian_dateOut[]   = {"JULIAN_DATE"};
static const char * getJulian_dayIn[]     = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getJulian_dayOut[]    = {"JULIAN_DAY"};
static const char * getUt1In[]            = {"IBYR", "IBDT", "IBHM", "IBCS"};
static const char * getUt1Out[]           = {"UT1"};
static const char * getUt2In[]            = {"IEYR", "IEDT", "IEHM", "IECS"};
static const char * getUt2Out[]           = {"UT2"};
static const char * getDut21In[]          = {"UT1", "UT2"};
static const char * getDut21Out[]         = {"DUT21"};
static const char * getFyearIn[]          = {"IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS"};
static const char * getFyearOut[]         = {"FYEAR"};

/* time and space */

static const char * getStationIn[]        = {"KINST"};
static const char * getStationOut[]       = {"GDLATR", "GDLONR", "GALTR"};
static const char * getAltIncIn[]         = {"ROW", "ALTB", "ALTAV"};
static const char * getAltIncOut[]        = {"GDALT"};
static const char * getAveAltIn[]         = {"ALTB", "ALTE"};
static const char * getAveAltOut[]        = {"GDALT"};
static const char * getAveDAltIn[]        = {"DALTB", "DALTE"};
static const char * getAveDAltOut[]       = {"DGDALT"};
static const char * getReslIn[]           = {"MRESL"};
static const char * getReslOut[]          = {"RESL"};
static const char * getAzmDazIn[]         = {"AZ1", "AZ2"};
static const char * getAzmDazOut[]        = {"AZM", "DAZ"};
static const char * getDAzmDDazIn[]       = {"DAZ1", "DAZ2"};
static const char * getDAzmDDazOut[]      = {"DAZM", "DDAZ"};
static const char * getElmDelIn[]         = {"EL1", "EL2"};
static const char * getElmDelOut[]        = {"ELM", "DEL"};
static const char * getDElmDDelIn[]       = {"DEL1", "DEL2"};
static const char * getDElmDDelOut[]      = {"DELM", "DDEL"};
static const char * getGeodIn[]           = {"KINST", "AZM", "ELM", "RANGE"};
static const char * getGeodOut[]          = {"GDLAT", "GLON", "GDALT"};
static const char * getDGeodIn[]          = {"KINST", "AZM", "DAZM", "ELM", "DELM", "RANGE", "DRANGE"};
static const char * getDGeodOut[]         = {"DGDLAT", "DGLON", "DGDALT"};
static const char * getGeodGdaltIn[]      = {"KINST", "AZM", "ELM", "GDALT"};
static const char * getGeodGdaltOut[]     = {"GDLAT", "GLON"};
static const char * getGeodAltIn[]        = {"GDLATR", "GDLONR"};
static const char * getGeodAltOut[]       = {"GDLAT", "GLON"};
static const char * getAzElRangeIn[]      = {"GDLAT", "GLON", "GDALT", "GDLATR", "GDLONR", "GALTR"};
static const char * getAzElRangeOut[]     = {"AZM","ELM", "RANGE"};
static const char * getSZenIn[]           = {"UT1", "UT2", "GDLAT", "GLON"};
static const char * getSZenOut[]          = {"SZEN"};
static const char * getSltmutIn[]         = {"UT1", "UT2", "GLON"};
static const char * getSltmutOut[]        = {"SLTMUT"};
static const char * getSltIn[]            = {"UT1", "UT2", "GLON"};
static const char * getSltOut[]           = {"SLT"};
static const char * getSdwHtIn[]          = {"UT1", "UT2", "GDLAT", "GLON"};
static const char * getSdwHtOut[]         = {"SDWHT"};
static const char * getSuntimeIn[]        = {"UT1", "UT2", "GDLAT", "GLON", "GDALT"};
static const char * getSuntimeOut[]       = {"SUNRISE", "SUNSET", "SUNRISE_HOUR", "SUNSET_HOUR"};
static const char * getTecGdaltIn[]       = {"TEC", "GDLAT", "GLON"};
static const char * getTecGdaltOut[]      = {"GDALT"};
static const char * getGcdistIn[]         = {"GDLATR", "GDLONR", "GDLAT", "GLON"};
static const char * getGcdistOut[]        = {"GCDIST"};

/* magnetic parameters */
static const char * getMagIn[]            = {"UT1", "UT2", "GDLAT", "GLON", "GDALT"};
static const char * getMagOut[]           = {"BN","BE","BD","BMAG"};
static const char * getMagIn2[]           = {"UT1", "UT2", "GDLAT", "GLON", "GDALT"};
static const char * getMagOut2[]          = {"BDEC","BINC","LSHELL",
                                             "DIPLAT","INVLAT","APLAT","APLON",
                                             "MAGCONJLAT","MAGCONJLON"};
static const char * getMagStatIn[]        = {"UT1", "UT2", "GDLAT", "GLON", "GDALT",
                                             "GDLATR", "GDLONR", "GALTR"};
static const char * getMagStatOut[]       = {"CXR","CYR","CZR"};
static const char * getSltcIn[]           = {"UT1", "UT2", "MAGCONJLON"};
static const char * getSltcOut[]          = {"SLTC"};
static const char * getApltIn[]           = {"UT1", "UT2", "APLON"};
static const char * getApltOut[]          = {"APLT"};
static const char * getSZencIn[]          = {"UT1", "UT2", "MAGCONJLAT","MAGCONJLON"};
static const char * getSZencOut[]         = {"SZENC"};
static const char * getConjSunIn[]        = {"UT1", "UT2", "MAGCONJLAT", "MAGCONJLON", "GDALT"};
static const char * getConjSunOut[]       = {"CONJ_SUNRISE", "CONJ_SUNSET", "CONJ_SUNRISE_H", "CONJ_SUNSET_H", "MAGCONJSDWHT"};
static const char * getTsyganIn[]         = {"UT1", "UT2", "GDLAT", "GLON", "GDALT"};
static const char * getTsyganOut[]        = {"TSYG_EQ_XGSM","TSYG_EQ_YGSM","TSYG_EQ_XGSE","TSYG_EQ_YGSE"};
static const char * getAacgmIn[]          = {"GDLAT", "GLON", "GDALT"};
static const char * getAacgmOut[]         = {"PACLAT","PACLON"};
static const char * fromAacgmIn[]         = {"PACLAT","PACLON","GDALT"};
static const char * fromAacgmOut[]        = {"GDLAT", "GLON"};
static const char * getEregionIn[]        = {"UT1", "UT2", "GDLAT", "GLON", "GDALT"};
static const char * getEregionOut[]       = {"E_REG_S_LAT", "E_REG_S_LON", "E_REG_S_SDWHT",
                                             "E_REG_N_LAT", "E_REG_N_LON", "E_REG_N_SDWHT"};
static const char * getAspectIn[]         = {"UT1", "UT2", "GDLATR", "GDLONR", "GALTR",
                                             "AZM", "ELM", "RANGE",};
static const char * getAspectOut[]        = {"ASPECT"};

/* geophysical parameters */

static const char * getGeoIn[]            = {"UT1", "UT2"};
static const char * getGeoOut[]           = {"KP", "AP3", "AP", "F10.7", "FBAR"};
static const char * getDstIn[]            = {"UT1", "UT2"};
static const char * getDstOut[]           = {"DST"};
static const char * getFof2In[]           = {"UT1", "UT2", "KINST"};
static const char * getFof2Out[]          = {"FOF2"};

/* isr parameters */
static const char * getPoplIn[]           = {"POP"};
static const char * getPoplOut[]          = {"POPL"};
static const char * getPopIn[]            = {"POPL"};
static const char * getPopOut[]           = {"POP"};
static const char * getNeFromNe8In[]      = {"NE8"};
static const char * getNeFromNe8Out[]     = {"NE"};
static const char * getDNeFromDNe8In[]    = {"DNE8"};
static const char * getDNeFromDNe8Out[]   = {"DNE"};
static const char * getNelIn[]            = {"NE"};
static const char * getNelOut[]           = {"NEL"};
static const char * getNeIn[]             = {"NEL"};
static const char * getNeOut[]            = {"NE"};
static const char * getDNelIn[]           = {"DNE"};
static const char * getDNelOut[]          = {"DNEL"};
static const char * getDNeIn[]            = {"DNEL"};
static const char * getDNeOut[]           = {"DNE"};
static const char * getNemaxlIn[]         = {"NEMAX"};
static const char * getNemaxlOut[]        = {"NEMAXL"};
static const char * getNemaxIn[]          = {"NEMAXL"};
static const char * getNemaxOut[]         = {"NEMAX"};
static const char * getTrIn[]             = {"TE","TI"};
static const char * getTrOut[]            = {"TR"};
static const char * getTeIn[]             = {"TR","TI"};
static const char * getTeOut[]            = {"TE"};
static const char * getTiIn[]             = {"TE","TR"};
static const char * getTiOut[]            = {"TI"};
static const char * getDteCctitrIn[]      = {"CCTITR","TI", "TR", "DTI", "DTR"};
static const char * getDteCctitrOut[]     = {"DTE"};
static const char * getDteIn[]            = {"TE","TI", "TR", "DTI", "DTR"};
static const char * getDteOut[]           = {"DTE"};
static const char * getColIn[]            = {"CO"};
static const char * getColOut[]           = {"COL"};
static const char * getCoIn[]             = {"COL"};
static const char * getCoOut[]            = {"CO"};
static const char * getNeNelIn[]          = {"TI","TR", "POPL", "ASPECT"};
static const char * getNeNelOut[]         = {"NE", "NEL"};
static const char * getDNeDNelIn[]        = {"TI","TR", "POPL", "ASPECT", "DTI","DTR", "DPOPL"};
static const char * getDNeDNelOut[]       = {"DNE", "DNEL"};
static const char * getVisrNeIn[]         = {"UT1", "KINST", "SLT", "GDALT", "GDLAT", "ELM"};
static const char * getVisrNeOut[]        = {"NE_MODEL", "NEL_MODEL"};
static const char * getVisrTeIn[]         = {"UT1", "KINST", "SLT", "GDALT", "GDLAT", "ELM"};
static const char * getVisrTeOut[]        = {"TE_MODEL",};
static const char * getVisrTiIn[]         = {"UT1", "KINST", "SLT", "GDALT", "GDLAT", "ELM"};
static const char * getVisrTiOut[]        = {"TI_MODEL"};
static const char * getVisrVoIn[]         = {"UT1", "KINST", "SLT", "GDALT", "GDLAT", "ELM"};
static const char * getVisrVoOut[]        = {"VO_MODEL"};
static const char * getVisrHNMaxIn[]      = {"UT1", "KINST", "SLT", "GDALT", "GDLAT", "ELM"};
static const char * getVisrHNMaxOut[]     = {"HMAX_MODEL", "NMAX_MODEL"};
static const char * getVisrNeDiffIn[]     = {"NE", "NE_MODEL"};
static const char * getVisrNeDiffOut[]    = {"NE_MODELDIFF"};
static const char * getVisrNelDiffIn[]    = {"NEL", "NEL_MODEL"};
static const char * getVisrNelDiffOut[]   = {"NEL_MODELDIFF"};
static const char * getVisrTeDiffIn[]     = {"TE", "TE_MODEL"};
static const char * getVisrTeDiffOut[]    = {"TE_MODELDIFF"};
static const char * getVisrTiDiffIn[]     = {"TI", "TI_MODEL"};
static const char * getVisrTiDiffOut[]    = {"TI_MODELDIFF"};
static const char * getVisrVoDiffIn[]     = {"VO", "VO_MODEL"};
static const char * getVisrVoDiffOut[]    = {"VO_MODELDIFF"};
static const char * getSnIn[]             = {"SNP3"};
static const char * getSnOut[]            = {"SN"};
static const char * getSnp3In[]           = {"SN"};
static const char * getSnp3Out[]          = {"SNP3"};
static const char * getChip31In[]          = {"CHISQ"};
static const char * getChip31Out[]         = {"CHIP3"};
static const char * getWchsq1In[]          = {"CHIP3"};
static const char * getWchsq1Out[]         = {"WCHSQ"};
static const char * getChisq1In[]          = {"WCHSQ"};
static const char * getChisq1Out[]         = {"CHISQ"};
static const char * getChip32In[]          = {"WCHSQ"};
static const char * getChip32Out[]         = {"CHIP3"};
static const char * getWchsq2In[]          = {"CHISQ"};
static const char * getWchsq2Out[]         = {"WCHSQ"};
static const char * getChisq2In[]          = {"CHIP3"};
static const char * getChisq2Out[]         = {"CHISQ"};

/* vector transformations */
/* ion velocity */
static const char * getVi1Vi1fIn[]         = {"VI1F"};
static const char * getVi1Vi1fOut[]        = {"VI1"};
static const char * getVi2Vi2fIn[]         = {"VI2F"};
static const char * getVi2Vi2fOut[]        = {"VI2"};
static const char * getVipeVipe1In[]       = {"VIPE1"};
static const char * getVipeVipe1Out[]      = {"VIPE"};
static const char * getVipeVipe2In[]       = {"VIPE2"};
static const char * getVipeVipe2Out[]      = {"VIPE"};
static const char * getVipnVipn1In[]       = {"VIPN1"};
static const char * getVipnVipn1Out[]      = {"VIPN"};
static const char * getVipnVipn2In[]       = {"VIPN2"};
static const char * getVipnVipn2Out[]      = {"VIPN"};
static const char * getVi6VipuIn[]         = {"VI6"};
static const char * getVi6VipuOut[]        = {"VIPU"};
static const char * getViGeomIn[]          = {"VI1", "VI2", "VI3", "BN", "BE", "BD", "BMAG"};
static const char * getViGeomOut[]         = {"VIPE", "VIPN", "VIPU"};
static const char * getViGeodIn[]          = {"VIPE", "VIPN", "VIPU", "BN", "BE", "BD", "BMAG"};
static const char * getViGeodOut[]         = {"VI1", "VI2", "VI3"};
/* neutral velocity */
static const char * getVn1Vn1p2In[]        = {"VN1P2"};
static const char * getVn1Vn1p2Out[]       = {"VN1"};
static const char * getVn2Vn2p2In[]        = {"VN2P2"};
static const char * getVn2Vn2p2Out[]       = {"VN2"};
static const char * getVnGeomIn[]          = {"VN1", "VN2", "VN3", "BN", "BE", "BD", "BMAG"};
static const char * getVnGeomOut[]         = {"VN4", "VN5", "VN6"};
static const char * getVnGeodIn[]          = {"VN4", "VN5", "VN6", "BN", "BE", "BD", "BMAG"};
static const char * getVnGeodOut[]         = {"VN1", "VN2", "VN3"};
/* electric field */
static const char * getEFGeomIn[]          = {"EE", "EN", "EU", "BN", "BE", "BD", "BMAG"};
static const char * getEFGeomOut[]         = {"EPE", "EPN", "EAP"};
static const char * getEFGeodIn[]          = {"EPE", "EPN", "EAP", "BN", "BE", "BD", "BMAG"};
static const char * getEFGeodOut[]         = {"EE", "EN", "EU"};
/* current density */
static const char * getJGeomIn[]           = {"J1", "J2", "J3", "BN", "BE", "BD", "BMAG"};
static const char * getJGeomOut[]          = {"J4", "J5", "J6"};
static const char * getJGeodIn[]           = {"J4", "J5", "J6", "BN", "BE", "BD", "BMAG"};
static const char * getJGeodOut[]          = {"J1", "J2", "J3"};

/* neutral atmosphere */
static const char * getTnIn[]             = {"TI", "TE", "NE", "PH+", "NOL", "NHL",
                                             "NN4SL", "NO2L", "NHEL"};
static const char * getTnOut[]            = {"TN"};
static const char * getTnNoPhpIn[]        = {"TI", "TE", "NE", "NOL", "NHL",
                                             "NN4SL", "NO2L", "NHEL"};
static const char * getTnNoPhpOut[]       = {"TN"};
static const char * getDTnIn[]            = {"TI", "TE", "NE", "NOL", "NHL",
                                             "NN4SL", "NO2L", "NHEL",
                                             "DTI", "DTE", "DNE", "DNOL", "DNHL",
                                             "DNN4SL", "DNO2L", "DNHEL"};
static const char * getDTnOut[]           = {"DTN"};

/* IRI model */
static const char * getIriIn[]             = {"UT1", "UT2", "GDLAT", "GLON", "GDALT"};
static const char * getIriOut[]            = {"NE_IRI", "NEL_IRI", "TN_IRI", "TI_IRI", "TE_IRI",
                                              "PO+_IRI", "PNO+_IRI", "PO2+_IRI", "PHE+_IRI", "PH+_IRI", "PN+_IRI"};

/* conductivity */
static const char * getCondIn[]           = {"TI", "TE", "NE", "PH+_IRI", "PO+_IRI", "NOL", "NN2L",
                                             "NO2L", "TNM", "BMAG"};
static const char * getCondOut[]          = {"PDCON", "PDCONL", "HLCON", "HLCONL"};
static const char * getDCondIn[]          = {"TI", "TE", "NE", "PH+_IRI", "PO+_IRI", "NOL", "NN2L",
                                             "NO2L", "TNM", "BMAG",
                                             "DTI", "DTE", "DNE", "DNOL", "DNN2L",
                                             "DNO2L"};
static const char * getDCondOut[]         = {"DPDCON", "DPDCONL", "DHLCON", "DHLCONL"};


/* interplanetary mag field */
static const char * getImfIn[]           = {"UT1", "UT2"};
static const char * getImfOut[]          = {"BXGSM", "BYGSM", "BZGSM", "BIMF",
                                            "BXGSE", "BYGSE", "BZGSE",
                                            "SWDEN", "SWSPD", "SWQ"};



/* finally, declare global data structure listing all methods */
/* Each CompiledExt contains:                                 */
/*     1. methodName                                          */
/*     2. number of input parameters                          */
/*     3. list of input parameters defined above              */
/*     4. number of output parameters                         */
/*     5. list of output parameters defined above             */
static CompiledExt gCompExtList[] = {{ getPrologTime,  2,    getPrologTimeIn,  8,     getPrologTimeOut},
		                             { getByear,       1,    getByearIn,       1,     getByearOut},
                                     { getTime,        8,    getTimeIn,        7,     getTimeOut},
                                     { getBmd,         1,    getBmdIn,         1,     getBmdOut},
				                     { getBMonthDay,   1,    getBMonthDayIn,   2,     getBMonthDayOut},
                                     { getMd,          8,    getMdIn,          1,     getMdOut},
                                     { getUtUnix,      8,    getUtUnixIn,      2,     getUtUnixOut},
                                     { getDayno,       8,    getDaynoIn,       1,     getDaynoOut},
                                     { getBhm,         1,    getBhmIn,         1,     getBhmOut},
                                     { getBhhmmss,     2,    getBhhmmssIn,     1,     getBhhmmssOut},
                                     { getEhhmmss,     2,    getEhhmmssIn,     1,     getEhhmmssOut},
                                     { getHm,          8,    getHmIn,          1,     getHmOut},
                                     { getUth,        12,    getUthIn,         1,     getUthOut},
                                     { getUts,        12,    getUtsIn,         1,     getUtsOut},
                                     { getBUth,        8,    getBUthIn,        1,     getBUthOut},
                                     { getInttms,      8,    getInttmsIn,      1,     getInttmsOut},
                                     { getInttmm,      8,    getInttmmIn,      1,     getInttmmOut},
                                     { getDatntd,      8,    getDatntdIn,      1,     getDatntdOut},
                                     { getUt,          1,    getUtIn,          1,     getUtOut},
                                     { getBegUt,       1,    getBegUtIn,       1,     getBegUtOut},
                                     { getJdayno,      8,    getJdaynoIn,      1,     getJdaynoOut},
                                     { getJulian_date, 9,    getJulian_dateIn, 1,     getJulian_dateOut},
                                     { getJulian_day,  8,    getJulian_dayIn,  1,     getJulian_dayOut},
                                     { getUt1,         4,    getUt1In,         1,     getUt1Out},
                                     { getUt2,         4,    getUt2In,         1,     getUt2Out},
                                     { getDut21,       2,    getDut21In,       1,     getDut21Out},
				                     { getFyear,       8,    getFyearIn,       1,     getFyearOut},
                                     { getStation,     1,    getStationIn,     3,     getStationOut},
                                     { getAltInc,      3,    getAltIncIn,      1,     getAltIncOut},
                                     { getAveAlt,      2,    getAveAltIn,      1,     getAveAltOut},
                                     { getAveDAlt,     2,    getAveDAltIn,     1,     getAveDAltOut},
				                     { getResl,        1,    getReslIn,        1,     getReslOut},
                                     { getAzmDaz,      2,    getAzmDazIn,      2,     getAzmDazOut},
                                     { getDAzmDDaz,    2,    getDAzmDDazIn,    2,     getDAzmDDazOut},
                                     { getElmDel,      2,    getElmDelIn,      2,     getElmDelOut},
                                     { getDElmDDel,    2,    getDElmDDelIn,    2,     getDElmDDelOut},
                                     { getGeod,        4,    getGeodIn,        3,     getGeodOut},
                                     { getDGeod,       7,    getDGeodIn,       3,     getDGeodOut},
                                     { getGeodGdalt,   4,    getGeodGdaltIn,   2,     getGeodGdaltOut},
                                     { getGeodAlt,     2,    getGeodAltIn,     2,     getGeodAltOut},
                                     { getAzElRange,   6,    getAzElRangeIn,   3,     getAzElRangeOut},
                                     { getSZen,        4,    getSZenIn,        1,     getSZenOut},
                                     { getSltmut,      3,    getSltmutIn,      1,     getSltmutOut},
                                     { getSlt,         3,    getSltIn,         1,     getSltOut},
                                     { getSdwHt,       4,    getSdwHtIn,       1,     getSdwHtOut},
                                     { getSuntime,     5,    getSuntimeIn,     4,     getSuntimeOut},
				                     { getTecGdalt,    3,    getTecGdaltIn,    1,     getTecGdaltOut},
				                     { getGcdist,      4,    getGcdistIn,      1,     getGcdistOut},
                                     { getMag,         5,    getMagIn,         4,     getMagOut},
									 { getMag2,        5,    getMagIn2,        9,     getMagOut2},
                                     { getMagStat,     8,    getMagStatIn,     3,     getMagStatOut},
				                     { getSltc,        3,    getSltcIn,        1,     getSltcOut},
                                     { getAplt,        3,    getApltIn,        1,     getApltOut},
                                     { getSZenc,       4,    getSZencIn,       1,     getSZencOut},
                                     { getConjSun,     5,    getConjSunIn,     5,     getConjSunOut},
				                     { getTsygan,      5,    getTsyganIn,      4,     getTsyganOut},
				                     { getAacgm,       3,    getAacgmIn,       2,     getAacgmOut},
				                     { fromAacgm,      3,    fromAacgmIn,      2,     fromAacgmOut},
				                     { getEregion,     5,    getEregionIn,     6,     getEregionOut},
				                     { getAspect,      8,    getAspectIn,      1,     getAspectOut},
                                     { getGeo,         2,    getGeoIn,         5,     getGeoOut},
                                     { getDst,         2,    getDstIn,         1,     getDstOut},
                                     { getFof2,        3,    getFof2In,        1,     getFof2Out},
                                     { getPopl,        1,    getPoplIn,        1,     getPoplOut},
                                     { getPop,         1,    getPopIn,         1,     getPopOut},
									 { getNeFromNe8,   1,    getNeFromNe8In,   1,     getNeFromNe8Out},
									 { getDNeFromDNe8, 1,    getDNeFromDNe8In, 1,     getDNeFromDNe8Out},
                                     { getNel,         1,    getNelIn,         1,     getNelOut},
                                     { getNe,          1,    getNeIn,          1,     getNeOut},
				                     { getDNel,        1,    getDNelIn,        1,     getDNelOut},
                                     { getDNe,         1,    getDNeIn,         1,     getDNeOut},
                                     { getNemaxl,      1,    getNemaxlIn,      1,     getNemaxlOut},
                                     { getNemax,       1,    getNemaxIn,       1,     getNemaxOut},
                                     { getTr,          2,    getTrIn,          1,     getTrOut},
                                     { getTe,          2,    getTeIn,          1,     getTeOut},
                                     { getTi,          2,    getTiIn,          1,     getTiOut},
				                     { getDteCctitr,   5,    getDteCctitrIn,   1,     getDteCctitrOut},
                                     { getDte,         5,    getDteIn,         1,     getDteOut},
                                     { getCol,         1,    getColIn,         1,     getColOut},
                                     { getCo,          1,    getCoIn,          1,     getCoOut},
                                     { getNeNel,       4,    getNeNelIn,       2,     getNeNelOut},
                                     { getDNeDNel,     7,    getDNeDNelIn,     2,     getDNeDNelOut},
				                     { getVisrNe,      6,    getVisrNeIn,      2,     getVisrNeOut},
				                     { getVisrTe,      6,    getVisrTeIn,      1,     getVisrTeOut},
				                     { getVisrTi,      6,    getVisrTiIn,      1,     getVisrTiOut},
				                     { getVisrVo,      6,    getVisrVoIn,      1,     getVisrVoOut},
				                     { getVisrHNMax,   6,    getVisrHNMaxIn,   2,     getVisrHNMaxOut},
				                     { getVisrNeDiff,  2,    getVisrNeDiffIn,  1,     getVisrNeDiffOut},
				                     { getVisrNelDiff, 2,    getVisrNelDiffIn, 1,    getVisrNelDiffOut},
				                     { getVisrTeDiff,  2,    getVisrTeDiffIn,  1,     getVisrTeDiffOut},
				                     { getVisrTiDiff,  2,    getVisrTiDiffIn,  1,     getVisrTiDiffOut},
				                     { getVisrVoDiff,  2,    getVisrVoDiffIn,  1,     getVisrVoDiffOut},
				                     { getSn,          1,    getSnIn,          1,     getSnOut},
				                     { getSnp3,        1,    getSnp3In,        1,     getSnp3Out},
				                     { getChip31,      1,    getChip31In,      1,     getChip31Out},
				                     { getWchsq1,      1,    getWchsq1In,      1,     getWchsq1Out},
				                     { getChisq1,      1,    getChisq1In,      1,     getChisq1Out},
				                     { getChip32,      1,    getChip32In,      1,     getChip32Out},
				                     { getWchsq2,      1,    getWchsq2In,      1,     getWchsq2Out},
				                     { getChisq2,      1,    getChisq2In,      1,     getChisq2Out},
				                     { getVi1Vi1f,     1,    getVi1Vi1fIn,     1,     getVi1Vi1fOut},
				                     { getVi2Vi2f,     1,    getVi2Vi2fIn,     1,     getVi2Vi2fOut},
				                     { getVipeVipe1,   1,    getVipeVipe1In,   1,     getVipeVipe1Out},
				                     { getVipeVipe2,   1,    getVipeVipe2In,   1,     getVipeVipe2Out},
				                     { getVipnVipn1,   1,    getVipnVipn1In,   1,     getVipnVipn1Out},
				                     { getVipnVipn2,   1,    getVipnVipn2In,   1,     getVipnVipn2Out},
				                     { getVi6Vipu,     1,    getVi6VipuIn,     1,     getVi6VipuOut},
				                     { getViGeom,      7,    getViGeomIn,      3,     getViGeomOut},
				                     { getViGeod,      7,    getViGeodIn,      3,     getViGeodOut},
				                     { getVn1Vn1p2,    1,    getVn1Vn1p2In,    1,     getVn1Vn1p2Out},
				                     { getVn2Vn2p2,    1,    getVn2Vn2p2In,    1,     getVn2Vn2p2Out},
				                     { getVnGeom,      7,    getVnGeomIn,      3,     getVnGeomOut},
				                     { getVnGeod,      7,    getVnGeodIn,      3,     getVnGeodOut},
				                     { getEFGeom,      7,    getEFGeomIn,      3,     getEFGeomOut},
				                     { getEFGeod,      7,    getEFGeodIn,      3,     getEFGeodOut},
				                     { getJGeom,       7,    getJGeomIn,       3,     getJGeomOut},
				                     { getJGeod,       7,    getJGeodIn,       3,     getJGeodOut},
				                     { getTn,          9,    getTnIn,          1,     getTnOut},
				                     { getTnNoPhp,     8,    getTnNoPhpIn,     1,     getTnNoPhpOut},
				                     { getDTn,        16,    getDTnIn,         1,     getDTnOut},
				                     { getIri,         5,    getIriIn,        11,     getIriOut},
				                     { getCond,       10,    getCondIn,        4,     getCondOut},
				                     { getDCond,      16,    getDCondIn,       4,     getDCondOut},
                                     { getImf,         2,    getImfIn,        10,     getImfOut},
                                     { NULL}};

/* this next section is for declaring methods that take as input all the 2D rows in a Madrecord */

static const char * getTestAveAltIn[]    = {"UT1", "GDALT"};
static const int    typeTestAveAltIn[]   = {1,2};
static const char * getTestAveAltOut[]   = {"LOW_GDALT", "AVE_GDALT"};
static const int    typeTestAveAltOut[]  = {1,2};


static CompiledMultiRowExt gCompExtMultiRowList[] = {{getTestAveAlt,
                                                      2, getTestAveAltIn, typeTestAveAltIn,
                                                      2, getTestAveAltOut, typeTestAveAltOut},
                                                     { NULL}};
/***********************************************************************
*
* createInfoMethod - sets up a InfoMethod struct that describes one
*                    particular method used to derive parameters
*
*   arguments:
*      int numInputs - the number of inputs required
*      int numOutputs - the number of outputs required
*
*   Number of inputs and outputs defined in gCompExtList.
*
*   returns - pointer to newly created InfoMethod struct; destroy
*             using destroyInfoMethod
*/
InfoMethod * createInfoMethod(int numInputs, int numOutputs)
{
    InfoMethod * newInfoMethod = NULL;
    int i = 0;

    /* malloc newInfoMethod */
    if ((newInfoMethod = (InfoMethod *)malloc(sizeof(InfoMethod)))==0)
    {
        perror("malloc");
        exit(-1);
    }
    /* malloc arrays inputMap and outputMap */
    if ((newInfoMethod->inputMap = (int *)malloc(sizeof(int)*2*numInputs))==0)
    {
        perror("malloc");
        exit(-1);
    }
    if ((newInfoMethod->outputMap = (int *)malloc(sizeof(int)*numOutputs))==0)
    {
        perror("malloc");
        exit(-1);
    }

    /* initialize to 0 */
    newInfoMethod->numInputMethods = 0;
    for (i=0; i<MAX_NEEDED_METH; i++)
        newInfoMethod->neededMethods[i] = 0;
    newInfoMethod->all1D = 0;
    newInfoMethod->isAvailable = 0;
    newInfoMethod->isNeeded = 0;
    for (i=0; i<2*numInputs; i++)
        newInfoMethod->inputMap[i] = 0;
    for (i=0; i<numOutputs; i++)
        newInfoMethod->outputMap[i] = 0;

    return(newInfoMethod);
}


/***********************************************************************
*
* destroyInfoMethod - frees all memory for given InfoMethod struct
*
*   arguments:
*      InfoMethod * infoMethod - pointer to struct to free
*
*   returns - void
*/
void destroyInfoMethod(InfoMethod * infoMethod)
{
    if (infoMethod == NULL)
        return;

    if (infoMethod->inputMap != NULL)
        free(infoMethod->inputMap);

    if (infoMethod->outputMap != NULL)
        free(infoMethod->outputMap);

    free(infoMethod);
}


/***********************************************************************
*
* createInfoMultiRowMethod - sets up a InfoMultiRowMethod struct that describes one
*                    particular MultiRow method used to derive parameters
*
*   arguments:
*      int numInputs - the number of inputs required
*      int * inputType - an array of ints = 1 or 2, depending in 1 or 2D input,
*                        len =  numInputs
*      int numOutputs - the number of outputs required
*      int * outputType - an array of ints = 1 or 2, depending in 1 or 2D output,
*                        len =  numOutputs
*
*   Number of inputs and outputs and types defined in gCompExtMultiRowList.
*
*   Creates inputArr and outputArr.  For now they are arrays of pointers to
*   arrays of doubles of length 1 double.  If this method actually turns out to
*   be needed, the 2D arrays will be reallocated to MAX_2D_ROWS
*
*   returns - pointer to newly created InfoMultiRowMethod struct; destroy
*             using destroyInfoMultiRowMethod
*/

InfoMultiRowMethod * createInfoMultiRowMethod(int numInputs,
                                              const int * inputType,
                                              int numOutputs,
                                              const int * outputType)
{
    InfoMultiRowMethod * newInfoMultiRowMethod = NULL;
    int i = 0;

    /* malloc newInfoMultiRowMethod */
    if ((newInfoMultiRowMethod = (InfoMultiRowMethod *)malloc(sizeof(InfoMultiRowMethod)))==0)
    {
        perror("malloc");
        exit(-1);
    }

    /* malloc array inputMap  */
    if ((newInfoMultiRowMethod->inputMap = (int *)malloc(sizeof(int)*numInputs))==0)
    {
        perror("malloc");
        exit(-1);
    }

    /* malloc array inputArr  */
    if ((newInfoMultiRowMethod->inputArr = (double **)malloc(sizeof(double *)*numInputs))==0)
    {
        perror("malloc");
        exit(-1);
    }
    for (i=0; i<numInputs; i++)
    {
        newInfoMultiRowMethod->inputArr[i] = (double *)malloc(sizeof(double)*1);

        if (newInfoMultiRowMethod->inputArr[i] == 0)
        {
            perror("malloc");
            exit(-1);
        }
    }

    /* malloc array outputArr  */
    if ((newInfoMultiRowMethod->outputArr = (double **)malloc(sizeof(double *)*numOutputs))==0)
    {
        perror("malloc");
        exit(-1);
    }
    for (i=0; i<numOutputs; i++)
    {
        newInfoMultiRowMethod->outputArr[i] = (double *)malloc(sizeof(double)*1);

        if (newInfoMultiRowMethod->outputArr[i] == 0)
        {
            perror("malloc");
            exit(-1);
        }
    }

    newInfoMultiRowMethod->numInputs = numInputs;
    newInfoMultiRowMethod->numOutputs = numOutputs;


    /* initialize to 0 */
    newInfoMultiRowMethod->isNeeded = 0;
    for (i=0; i<numInputs; i++)
        newInfoMultiRowMethod->inputMap[i] = 0;


    return(newInfoMultiRowMethod);
}


/***********************************************************************
*
* destroyInfoMultiRowMethod - frees all memory for given InfoMultiRowMethod struct
*
*   arguments:
*      InfoMultiRowMethod * infoMultiRowMethod - pointer to struct to free
*
*   returns - void
*/
void destroyInfoMultiRowMethod(InfoMultiRowMethod * infoMultiRowMethod)
{
    int i = 0;

    if (infoMultiRowMethod == NULL)
        return;

    if (infoMultiRowMethod->inputMap != NULL)
        free(infoMultiRowMethod->inputMap);

    if (infoMultiRowMethod->inputArr != NULL)
    {
        for (i=0; i<infoMultiRowMethod->numInputs; i++)
            free(infoMultiRowMethod->inputArr[i]);
    }
    free (infoMultiRowMethod->inputArr);

    if (infoMultiRowMethod->outputArr != NULL)
    {
        for (i=0; i<infoMultiRowMethod->numOutputs; i++)
            free(infoMultiRowMethod->outputArr[i]);
    }
    free (infoMultiRowMethod->outputArr);

    free(infoMultiRowMethod);
}



/***********************************************************************
*
* createInfoDervFile - sets up a InfoDervFile struct in preparation for
*                     calculating all derived parameters for a file
*
*   arguments:
*      madrec * madrecp - pointer to madrec struct that has an in-memory file
*      MadparmList * requestParm - list of parameters requested
*      MadfilterList * filtList - list of Madfilters to apply
*      FILE * errFile   - errFile to write an error messages to
*
*   Examines each record in the in-memory file to get measured 1d and 2d parameters.
*   If first time that unique record type found, calls createInfoDerived
*   to create an analysis plan.  For each record, records its type and
*   location in returned struct InfoDervFile.  Call destroyInfoDervFile
*   when done with this struct.
*
*   returns - pointer to created InfoDervFile struct; if failure,
*             returns NULL and writes error to errFile
*/
InfoDervFile * createInfoDervFile(Madrec * madrecp,
                                  MadparmList * requestParm,
                                  MadfilterList * filtList,
                                  FILE * errFile)
{
    static const char *err1="madrec does not contain an in-memory file\n";

    InfoDervFile * infoDervFile;
    int i = 0;
    int j = 0;
    char * tmpMnem = NULL;
    int status = 0;
    int numDataRecs = 0;         /* total number of data records found so far     */
    int newCycle  = 0;           /* new cycle number                              */
    int presCycle = 0;           /* present cycle number                          */
    int recCount = 0;            /* index of present record                       */
    int presNum1D = 0;           /* number of 1D parameters of present record     */
    int presNum2D = 0;           /* number of 2D parameters of present record     */
    int * presParm1D = NULL;     /* array of 1D codes (int) in present record     */
    int * presParm2D = NULL;     /* array of 2D codes (int) in present record     */
    int   *   num1DParms = NULL; /* list of number of measured 1D parameters in   */
                                 /* each type of record found so far.             */
                                 /* Len = numTypesRec                             */
    int   *   num2DParms = NULL; /* list of number of measured 2D parameters in   */
                                 /* each type of record.  Len = numTypesRec       */
    int   **  arr1DParms = NULL; /* list of arrays of measured 1D parameters in   */
                                 /* each type of record.  Len = numTypesRec       */
                                 /* Length of each array given by value in        */
                                 /* num1DParms                                    */
    int   **  arr2DParms = NULL; /* list of arrays of measured 2D parameters in   */
                                 /* each type of record.  Len = numTypesRec       */
                                 /* Length of each array given by value in        */
                                 /* num2DParms                                    */
    int typeFound = 0;           /* used to determine if this record's type found */

    MadparmList * new1DList = NULL;   /* used to create new InfoDerived */
    MadparmList * new2DList = NULL;   /* used to create new InfoDerived */

    /* verify that madrec contains an in-memory file */
    if (madrecp->filep == NULL)
    {
        fwrite(err1,1, strlen(err1), errFile);
        return(NULL);
    }

    /* allocate infoDervFile */
    if ((infoDervFile = (InfoDervFile *)malloc(sizeof(InfoDervFile)))==0)
    {
        perror("malloc");
        exit(-1);
    }
    /* initialize infoDervFile */
    infoDervFile->numTypesRec = 0;
    infoDervFile->cycleNum = NULL;
    infoDervFile->numEachTypeRec = NULL;
    infoDervFile->eachTypeList = NULL;
    infoDervFile->infoDervList = NULL;

    /* prepare to loop through madrecp in-memory file */
    madrecRewind(madrecp);

    numDataRecs = 0;

    /* now loop through each record in in-memory file */
    for(recCount = 0; recCount < madrecp->nrecords; recCount++)
    {
        status=madrecGetRecByRecno(madrecp, recCount);
        /* check for error */
        if (status)
        {
            fwrite(madrecGetError(madrecp),1, strlen(madrecGetError(madrecp)), errFile);
            return(NULL);
        }

        /* skip HEADER or CATALOG records */
        if (!isDataRecord(madrecp->recordp))
            continue;
        else
            numDataRecs++;

        /* get 1 and 2 D parameters from present record */
        presNum1D = cedarGetJpar(madrecp->recordp);
        presNum2D = cedarGetMpar(madrecp->recordp);
	/* Its possible someone claims there are 2d parms, but the number of rows == 0 */
	/* In this case presNum2D should really be 0 */
	if (cedarGetNrow(madrecp->recordp) == 0)
	    presNum2D = 0;
        presParm1D = cedarGet1dParcodes(madrecp->recordp);
        presParm2D = cedarGet2dParcodes(madrecp->recordp);

        /* get cycle number of record                            */
        infoDervFile->cycleNum = (int *)realloc(infoDervFile->cycleNum, sizeof(int)*numDataRecs);
        if (!infoDervFile->cycleNum)
        {
            perror("malloc");
            exit(-1);
        }
        newCycle = cedarGet1dInt(madrecp->recordp, CYC_CODE);
        if (newCycle == missingData)
            infoDervFile->cycleNum[numDataRecs - 1] = presCycle;
        else /* record contains cycle info */
        {
            if (newCycle == presCycle)
                infoDervFile->cycleNum[numDataRecs - 1] = presCycle;
            else if (newCycle == presCycle + 1)
            {
                presCycle++;
                infoDervFile->cycleNum[numDataRecs - 1] = presCycle;
            }
            else /* cycle numbers messed up */
            {
	        /* changed to handle the situation where cycle number
		   is used differently than we expect.  For now, simply
		   ignore it and stay in the same cycle instead of throwing
		   an error - changed 1/15/2004
                perror("Problem found with cycle numbers");
                exit(-1); */
		infoDervFile->cycleNum[numDataRecs - 1] = presCycle;
            }
        }

        /* see if this record's type has already been found      */
        /* in this loop, i is the index for each type of record, */
        /* and j is the index for each parameter in that type    */
        typeFound = 0;
        for (i=0; i < infoDervFile->numTypesRec; i++)
        {
            /* if wrong number of 1D parameters, continue */
            if (presNum1D != num1DParms[i]) continue;

            /* if wrong number of 2D parameters, continue */
            if (presNum2D != num2DParms[i]) continue;

            /* if any 1D parameters don't match, set type found = -1 */
            for (j=0; j < presNum1D; j++)
            {
                if (presParm1D[j] != arr1DParms[i][j])
                {
                    typeFound = -1;
                    continue;
                }
            }

            /* if any 2D parameters don't match, set type found = -1 */
            for (j=0; j < presNum2D; j++)
            {
                if (presParm2D[j] != arr2DParms[i][j])
                {
                    typeFound = -1;
                    continue;
                }
            }

            /* if this point reached and typeFound == 0, match found */
            if (typeFound == 0)
            {
                typeFound = 1;
                break;
            }
            else
                typeFound = 0;
        }

        /* if match, append this record number */
        if (typeFound)
        {
            /* increment numEachTypeRec*/
            (infoDervFile->numEachTypeRec[i])++;

            /* realloc eachTypeList to make room for one more int */
            infoDervFile->eachTypeList[i] = (int *)realloc(infoDervFile->eachTypeList[i],
                                                          sizeof(int)*infoDervFile->numEachTypeRec[i]);

            /* copy recCount into eachTypeList */
            infoDervFile->eachTypeList[i][infoDervFile->numEachTypeRec[i] - 1] = recCount;
        }
        /* else match not found - add new type */
        else
        {
            /* update number of types */
            infoDervFile->numTypesRec++;

            /* update local variables: num1DParms, num2DParms, arr1DParms, arr2DParms */

            num1DParms = (int *)realloc(num1DParms, sizeof(int)*infoDervFile->numTypesRec);
            num1DParms[infoDervFile->numTypesRec - 1] = presNum1D;

            num2DParms = (int *)realloc(num2DParms, sizeof(int)*infoDervFile->numTypesRec);
            num2DParms[infoDervFile->numTypesRec - 1] = presNum2D;

            arr1DParms = (int **)realloc(arr1DParms, sizeof(int *)*infoDervFile->numTypesRec);
            arr1DParms[infoDervFile->numTypesRec - 1] = (int *)malloc(sizeof(int)*presNum1D);
            memcpy(arr1DParms[infoDervFile->numTypesRec - 1],
                   presParm1D,
                   sizeof(int)*presNum1D);

            arr2DParms = (int **)realloc(arr2DParms, sizeof(int *)*infoDervFile->numTypesRec);
            arr2DParms[infoDervFile->numTypesRec - 1] = (int *)malloc(sizeof(int)*presNum2D);
            memcpy(arr2DParms[infoDervFile->numTypesRec - 1],
                   presParm2D,
                   sizeof(int)*presNum2D);

            /* update infoDervFile members numEachTypeRec and eachTypeList */

            infoDervFile->numEachTypeRec = (int *)realloc(infoDervFile->numEachTypeRec,
                                                          sizeof(int)*infoDervFile->numTypesRec);
            infoDervFile->numEachTypeRec[infoDervFile->numTypesRec - 1] = 1; /* first record of this type */


            infoDervFile->eachTypeList = (int **)realloc(infoDervFile->eachTypeList,
                                                         sizeof(int *)*infoDervFile->numTypesRec);
            infoDervFile->eachTypeList[infoDervFile->numTypesRec - 1] = (int *)malloc(1*sizeof(int));
            infoDervFile->eachTypeList[infoDervFile->numTypesRec - 1][0] = recCount;

            /* create new1DList and new2DList parm lists */
            new1DList = createMadparmList();
            new2DList = createMadparmList();

            /* append 1D parameters from prolog */
            /* number of prolog parameter set in #define NUM_PROLOG_PARM */
            appendMadparm(new1DList, "FIRST_IBYR");
            appendMadparm(new1DList, "FIRST_IBDT");
            appendMadparm(new1DList, "FIRST_IBHM");
            appendMadparm(new1DList, "FIRST_IBCS");
            appendMadparm(new1DList, "KINST");
            appendMadparm(new1DList, "KINDAT");
            appendMadparm(new1DList, "IBYR");
            appendMadparm(new1DList, "IBDT");
            appendMadparm(new1DList, "IBHM");
            appendMadparm(new1DList, "IBCS");
            appendMadparm(new1DList, "IEYR");
            appendMadparm(new1DList, "IEDT");
            appendMadparm(new1DList, "IEHM");
            appendMadparm(new1DList, "IECS");
            appendMadparm(new1DList, "NROW");
            appendMadparm(new1DList, "UT1");
            appendMadparm(new1DList, "UT2");
            appendMadparm(new1DList, "RECNO");

            /* append 2D parameters from prolog */
            /* number of prolog parameter set in #define NUM_2D_PROLOG_PARM */
            appendMadparm(new2DList, "ROW");


            /* append 1D parameters */
            for (j=0; j<presNum1D; j++)
            {
                tmpMnem = cedarGetParMnemonic(presParm1D[j]);
                appendMadparm(new1DList, tmpMnem);
                free(tmpMnem);
            }

            /* append 2D parameters */
            for (j=0; j<presNum2D; j++)
            {
                tmpMnem = cedarGetParMnemonic(presParm2D[j]);
                appendMadparm(new2DList, tmpMnem);
                free(tmpMnem);
            }

            /* allocate one more InfoDerived * to hold new analysis of this new record type */
            infoDervFile->infoDervList = (InfoDerived **)realloc(infoDervFile->infoDervList,
                                                                 sizeof(InfoDerived *) * infoDervFile->numTypesRec);

            /* finally analyze this new record type to get analysis plan */
            infoDervFile->infoDervList[infoDervFile->numTypesRec - 1] = createInfoDerived(new1DList,
                                                                                          new2DList,
                                                                                          requestParm,
                                                                                          filtList);

            /* free new1DList and new2DList parm lists */
            destroyMadparmList(new1DList);
            destroyMadparmList(new2DList);
        }

        /* free resources from present record */
        free(presParm1D);
        free(presParm2D);

    } /* get next record from file */


    /* free all malloc'ed memory in local varaibles before returning */
    if (num1DParms != NULL)
        free(num1DParms);
    if (num2DParms != NULL)
        free(num2DParms);
    for (i=0; i< infoDervFile->numTypesRec; i++)
    {
        free(arr1DParms[i]);
        free(arr2DParms[i]);
    }
    if (arr1DParms != NULL)
        free(arr1DParms);
    if (arr2DParms != NULL)
        free(arr2DParms);


    return infoDervFile;

}


/***********************************************************************
*
* destroyInfoDervFile - frees all memory for given InfoDervFile struct
*
*   arguments:
*      InfoDervFile * info - pointer to struct to free
*
*   returns - void
*/
void destroyInfoDervFile(InfoDervFile * infoDervFile)
{
    int i=0;

    if (infoDervFile == NULL)
        return;

    if (infoDervFile->eachTypeList != NULL)
    {
        for(i=0; i< infoDervFile->numTypesRec; i++)
            free(infoDervFile->eachTypeList[i]);
    }

    if (infoDervFile->infoDervList != NULL)
    {
        for(i=0; i< infoDervFile->numTypesRec; i++)
            destroyInfoDerived(infoDervFile->infoDervList[i]);
    }

    if (infoDervFile->cycleNum != NULL)
        free(infoDervFile->cycleNum);

    if (infoDervFile->eachTypeList != NULL)
        free(infoDervFile->eachTypeList);

    if (infoDervFile->infoDervList != NULL)
        free(infoDervFile->infoDervList);

    if (infoDervFile->numEachTypeRec != NULL)
        free(infoDervFile->numEachTypeRec);

    free(infoDervFile);
}


/***********************************************************************
*
* getRecType - returns record type index in InfoDervFile for recno
*
*   arguments:
*      InfoDervFile * infoDervFile - pointer to InfoDervFile containing analysis
*      int recno - record number in file (starting at 0)
*
*   returns - record type index in InfoDervFile for recno.  If not
*             found, returns -1
*/
int getRecType(InfoDervFile * infoDervFile, int recno)
{
    int i = 0;
    int low = 0;
    int mid = 0;
    int high = 0;
    int midvalue = 0;

    for (i=0; i<infoDervFile->numTypesRec; i++)
    {
        /* speed up search by using binary search */
        low = 0;
        high = infoDervFile->numEachTypeRec[i];

        while (low <= high)
        {
            mid = (low + high)/2;
            midvalue = infoDervFile->eachTypeList[i][mid];
            if (recno == midvalue)
                return (i);
            else if (recno < midvalue)
                high = mid-1;
            else
                low = mid+1;
        }
    }

    /* not found */
    return (-1);
}


/***********************************************************************
*
* load1DMeasData - copies 1D measured data into infoDervFile's memory
*
*   arguments:
*      InfoDervFile * infoDervFile - pointer to InfoDervFile containing analysis
*      Madrec * madrecp - pointer to Madrec holding data from file
*      int recType - record type of present record
*      double first_ibyr - year of first record (faster than rewinding to get these four)
*      double first_ibdt - date of first record
*      double first_ibhm - hm*100+min of first record
*      double first_ibcs - centisecs of first record
*
*   returns - void
*
*   affects - copies measured 1D data into appropriate place in
*             infoDervFile->infoDervList[recType]->all1DParm
*/
void load1DMeasData(InfoDervFile * infoDervFile,
                    Madrec * madrecp,
                    int recType,
                    double first_ibyr,
                    double first_ibdt,
                    double first_ibhm,
                    double first_ibcs)
{
    int i = 0;
    int parCode = 0;  /* the cedar parameter code of the present 1D parameter */

    /* the first 1D parameters are set, as standard prolog parameters */

    /* set four parameters that set the time of the first record */
    infoDervFile->infoDervList[recType]->all1DParm[0] = first_ibyr;
    infoDervFile->infoDervList[recType]->all1DParm[1] = first_ibdt;
    infoDervFile->infoDervList[recType]->all1DParm[2] = first_ibhm;
    infoDervFile->infoDervList[recType]->all1DParm[3] = first_ibcs;

    /* set the parameters from the prolog */
    infoDervFile->infoDervList[recType]->all1DParm[4]  = (double) cedarGetKinst(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[5]  = (double) cedarGetKindat(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[6]  = (double) cedarGetIbyr(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[7]  = (double) cedarGetIbdt(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[8]  = (double) cedarGetIbhm(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[9]  = (double) cedarGetIbcs(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[10] = (double) cedarGetIeyr(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[11] = (double) cedarGetIedt(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[12] = (double) cedarGetIehm(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[13] = (double) cedarGetIecs(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[14] = (double) cedarGetNrow(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[15] = (double) cedarGetStartIndex(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[16] = (double) cedarGetEndIndex(madrecp->recordp);
    infoDervFile->infoDervList[recType]->all1DParm[17] = (double) (madrecp->currentRecord);

    /* set the rest using infoDervFile->infoDervList[recType]->meas1DCodeList  */
    /* used here for speed to avoid converting from menmonic to parameter code */
    for (i=0; i<(infoDervFile->infoDervList[recType]->meas1DParmList->numParm - NUM_PROLOG_PARM); i++)
    {
        parCode = infoDervFile->infoDervList[recType]->meas1DCodeList[i];
        infoDervFile->infoDervList[recType]->all1DParm[i + NUM_PROLOG_PARM] = cedarGet1dParm(madrecp->recordp, parCode);
    }
}



/***********************************************************************
*
* load2DMeasData - copies 2D measured data into infoDervFile's memory
*
*   arguments:
*      InfoDervFile * infoDervFile - pointer to InfoDervFile containing analysis
*      Madrec * madrecp - pointer to Madrec holding data from file
*      int recType - record type of present record
*      int row - 2D row to load (starts at 0)
*
*   returns - void
*
*   affects - copies measured 2D data into appropriate place in
*             infoDervFile->infoDervList[recType]->all2DParm
*/
void load2DMeasData(InfoDervFile * infoDervFile,
                    Madrec * madrecp,
                    int recType,
                    int row)
{
    int i = 0;
    int parCode = 0;  /* the cedar parameter code of the present 2D parameter */

    /* set one 2D prolog parameter - row number */
    infoDervFile->infoDervList[recType]->all2DParm[0] = (double)row;

    /* set using infoDervFile->infoDervList[recType]->meas2DCodeList  */
    /* used here for speed to avoid converting from menmonic to parameter code */
    for (i=0; i<(infoDervFile->infoDervList[recType]->meas2DParmList->numParm - NUM_2D_PROLOG_PARM); i++)
    {
        parCode = infoDervFile->infoDervList[recType]->meas2DCodeList[i];
        infoDervFile->infoDervList[recType]->all2DParm[i + NUM_2D_PROLOG_PARM] = cedarGet2dParmValue(madrecp->recordp, parCode, row);
    }
}


/***********************************************************************
*
* load1DMultiRowData - copies 1D data from infoDervFile into
*                      InfoMultiRowMethod->inputArr for all needed
*                      multi-row methods
*
*   arguments:
*      InfoDervFile * infoDervFile - pointer to InfoDervFile containing analysis
*      int recType - record type of present record
*
*   returns - void
*
*   affects - copies 1D data from infoDervFile into
*             InfoMultiRowMethod->inputArr
*/
void load1DMultiRowData(InfoDervFile * infoDervFile,
                        int recType)
{
    int i=0;
    int j=0;
    int map=0;
    InfoDerived * infoDerived = infoDervFile->infoDervList[recType];

    /* loop through each needed multi-row method */
    for (i=0; i<infoDerived->numMultiRowMeth; i++)
    {
        /* skip this method if not needed */
        if (!infoDerived->infoMultiRowMethArr[i]->isNeeded)
            continue;

        /* loop through all input mnem for 1D's to copy */
        for (j=0; j<infoDerived->infoMultiRowMethArr[i]->numInputs; j++)
        {
            /* skip 2D inputs */
            if (gCompExtMultiRowList[i].inputMnemType[j] == 2)
                continue;

            /* copy 1D data into inputArr*/
            map = infoDerived->infoMultiRowMethArr[i]->inputMap[j];
            infoDerived->infoMultiRowMethArr[i]->inputArr[j][0] = infoDerived->all1DParm[map];
        }
    }
}


/***********************************************************************
*
* load1DMultiRowDataNonfile - copies 1D data from infoDerv into
*                             InfoMultiRowMethod->inputArr for all needed
*                             multi-row methods - used when no file used
*
*   arguments:
*      InfoDerived * infoDerv - pointer to InfoDerived containing analysis
*
*   returns - void
*
*   affects - copies 1D data from infoDerv into
*             InfoMultiRowMethod->inputArr
*/
void load1DMultiRowDataNonfile(InfoDerived * infoDerived)
{
    int i=0;
    int j=0;
    int map=0;

    /* loop through each needed multi-row method */
    for (i=0; i<infoDerived->numMultiRowMeth; i++)
    {
        /* skip this method if not needed */
        if (!infoDerived->infoMultiRowMethArr[i]->isNeeded)
            continue;

        /* loop through all input mnem for 1D's to copy */
        for (j=0; j<infoDerived->infoMultiRowMethArr[i]->numInputs; j++)
        {
            /* skip 2D inputs */
            if (gCompExtMultiRowList[i].inputMnemType[j] == 2)
                continue;

            /* copy 1D data into inputArr*/
            map = infoDerived->infoMultiRowMethArr[i]->inputMap[j];
            infoDerived->infoMultiRowMethArr[i]->inputArr[j][0] = infoDerived->all1DParm[map];
        }
    }
}


/***********************************************************************
*
* load2DMultiRowData - copies 2D data from infoDervFile into
*                      InfoMultiRowMethod->inputArr for all needed
*                      multi-row methods
*
*   arguments:
*      InfoDervFile * infoDervFile - pointer to InfoDervFile containing analysis
*      int recType - record type of present record
*      int count2D - index into 2D record being added
*
*   returns - void
*
*   affects - copies 2D data from infoDervFile into
*             InfoMultiRowMethod->inputArr
*/
void load2DMultiRowData(InfoDervFile * infoDervFile,
                        int recType,
                        int count2D)
{
    int i=0;
    int j=0;
    int map=0;
    InfoDerived * infoDerived = infoDervFile->infoDervList[recType];

    /* loop through each needed multi-row method */
    for (i=0; i<infoDerived->numMultiRowMeth; i++)
    {
        /* skip this method if not needed */
        if (!infoDerived->infoMultiRowMethArr[i]->isNeeded)
            continue;

        /* loop through all input mnem for 2D's to copy */
        for (j=0; j<infoDerived->infoMultiRowMethArr[i]->numInputs; j++)
        {
            /* skip 1D inputs */
            if (gCompExtMultiRowList[i].inputMnemType[j] == 1)
                continue;

            /* copy 2D data into inputArr*/
            map = infoDerived->infoMultiRowMethArr[i]->inputMap[j];
            infoDerived->infoMultiRowMethArr[i]->inputArr[j][count2D] = infoDerived->all2DParm[map];
        }
    }
}


/***********************************************************************
*
* load2DMultiRowDataNonfile - copies 2D data from infoDerived into
*                             InfoMultiRowMethod->inputArr for all needed
*                             multi-row methods - used when no file used
*
*   arguments:
*      InfoDerived * infoDerived - pointer to InfoDerived containing analysis
*      int count2D - index into 2D record being added
*
*   returns - void
*
*   affects - copies 2D data from infoDerive into
*             InfoMultiRowMethod->inputArr
*/
void load2DMultiRowDataNonfile(InfoDerived * infoDerived,
                               int count2D)
{
    int i=0;
    int j=0;
    int map=0;

    /* loop through each needed multi-row method */
    for (i=0; i<infoDerived->numMultiRowMeth; i++)
    {
        /* skip this method if not needed */
        if (!infoDerived->infoMultiRowMethArr[i]->isNeeded)
            continue;

        /* loop through all input mnem for 2D's to copy */
        for (j=0; j<infoDerived->infoMultiRowMethArr[i]->numInputs; j++)
        {
            /* skip 1D inputs */
            if (gCompExtMultiRowList[i].inputMnemType[j] == 1)
                continue;

            /* copy 2D data into inputArr*/
            map = infoDerived->infoMultiRowMethArr[i]->inputMap[j];
            infoDerived->infoMultiRowMethArr[i]->inputArr[j][count2D] = infoDerived->all2DParm[map];
        }
    }
}


/***********************************************************************
*
* evaluateFilter - returns 1 if filter accepts, 0 if fails
*
*   arguments:
*      InfoDervFile * infoDervFile - pointer to InfoDervFile containing analysis
*      int recType - record type of present record
*      int dim - 1 for 1D filter, 2 for 2D filter
*      int filtIndex - index into filter list filt1DList or filt2DList, which
*                      determines which filter to apply
*
*   returns - 1 if filter accepts, 0 if fails
*
*   notes - if any filter parameter is missing, filter fails
*/
int evaluateFilter(InfoDervFile * infoDervFile,
                   int recType,
                   int dim,
                   int filtIndex)
{
    double parm1 = missing;
    double parm2 = missing;
    double * lower = NULL;
    double * upper = NULL;
    int index = 0;
    int numRange = 0;
    int i = 0;
    int allMissing = 0;

    /* check for bad argument - indicates bug */
    assert(0 < dim && dim < 3);

    /* handle each filter dimension */
    if (dim == 1)
    {
        /* get parm1 */
        index = infoDervFile->infoDervList[recType]->mapFilt1DParm[2*filtIndex];
        parm1 = infoDervFile->infoDervList[recType]->all1DParm[index];
        if (isnan(parm1))
            return (0);
	/* if its an error parmeter, reject it if its assumed or knownbad */
	if (isErrorParm(infoDervFile->infoDervList[recType]->allUsed1DParmList, index))
	{
	    if (parm1 == assumed || parm1 == knownbad)
            return (0);
	}

        /* get parm2 if needed */
        if (infoDervFile->infoDervList[recType]->filt1DList->madfilt_list[filtIndex].filtType != SINGLE_FILT)
        {
            index = infoDervFile->infoDervList[recType]->mapFilt1DParm[2*filtIndex + 1];
            parm2 = infoDervFile->infoDervList[recType]->all1DParm[index];
            if (isnan(parm2))
                return (0);
            /* if its an error parmeter, reject it if its assumed or knownbad */
	    if (isErrorParm(infoDervFile->infoDervList[recType]->allUsed1DParmList, index))
	    {
	        if (parm2 == assumed || parm2 == knownbad)
                return (0);
	    }
        }

        /* get filter numRange */
        numRange = infoDervFile->infoDervList[recType]->filt1DList->madfilt_list[filtIndex].numRange;

        /* get filter limits */
        lower = infoDervFile->infoDervList[recType]->filt1DList->madfilt_list[filtIndex].lower;
        upper = infoDervFile->infoDervList[recType]->filt1DList->madfilt_list[filtIndex].upper;

        /* if both missing from all ranges, filter always passes */
        allMissing = 1;
        for (i=0; i<numRange; i++)
        {
            if (!isnan(lower[i]) || !isnan(upper[i]))
            {
                allMissing = 0;
                break;
            }
        }
        if (allMissing) return (1);

        /* switch on filter type */
        switch (infoDervFile->infoDervList[recType]->filt1DList->madfilt_list[filtIndex].filtType)
        {
            case (SINGLE_FILT):
                for (i=0; i<numRange; i++)
                {
                    if (!isnan(lower[i]) && !isnan(upper[i]))
                    {
                        if (lower[i] <= parm1 && parm1 <= upper[i])
                            return(1);
                    }
                    else if (!isnan(lower[i]))
                    {
                        if (lower[i] <= parm1)
                            return(1);
                    }
                    else
                    {
                        if (parm1 <= upper[i])
                            return(1);
                    }
                }
                /* no acceptable range found */
                return(0);
                break;

            case (MULT_FILT):
                for (i=0; i<numRange; i++)
                {
                    if (!isnan(lower[i]) && !isnan(upper[i]))
                    {
                        if (lower[i] <= parm1*parm2 && parm1*parm2 <= upper[i])
                            return(1);
                    }
                    else if (!isnan(lower[i]))
                    {
                        if (lower[i] <= parm1*parm2)
                            return(1);
                    }
                    else
                    {
                        if (parm1*parm2 <= upper[i])
                            return(1);
                    }
                }
                /* no acceptable range found */
                return(0);
                break;

            case (DIV_FILT):
                for (i=0; i<numRange; i++)
                {
                    if (!isnan(lower[i]) && !isnan(upper[i]))
                    {
                        if (lower[i] <= parm1/parm2 && parm1/parm2 <= upper[i])
                            return(1);
                    }
                    else if (!isnan(lower[i]))
                    {
                        if (lower[i] <= parm1/parm2)
                            return(1);
                    }
                    else
                    {
                        if (parm1/parm2 <= upper[i])
                            return(1);
                    }
                }
                /* no acceptable range found */
                return(0);
                break;

            case (ADD_FILT):
                for (i=0; i<numRange; i++)
                {
                    if (!isnan(lower[i]) && !isnan(upper[i]))
                    {
                        if (lower[i] <= parm1+parm2 && parm1+parm2 <= upper[i])
                            return(1);
                    }
                    else if (!isnan(lower[i]))
                    {
                        if (lower[i] <= parm1+parm2)
                            return(1);
                    }
                    else
                    {
                        if (parm1+parm2 <= upper[i])
                            return(1);
                    }
                }
                /* no acceptable range found */
                return(0);
                break;

            case (SUB_FILT):
                for (i=0; i<numRange; i++)
                {
                    if (!isnan(lower[i]) && !isnan(upper[i]))
                    {
                        if (lower[i] <= parm1-parm2 && parm1-parm2 <= upper[i])
                            return(1);
                    }
                    else if (!isnan(lower[i]))
                    {
                        if (lower[i] <= parm1-parm2)
                            return(1);
                    }
                    else
                    {
                        if (parm1-parm2 <= upper[i])
                            return(1);
                    }
                }
                /* no acceptable range found */
                return(0);
                break;

            default:
                /* bug occured */
                assert(0);
        }
    } /* end 1D case */

    else  /* dim == 2 */
    {
        /* get parm1 */
        index = infoDervFile->infoDervList[recType]->mapFilt2DParm[4*filtIndex + 1];
        /* find out if its 1D or 2D */
        if (infoDervFile->infoDervList[recType]->mapFilt2DParm[4*filtIndex] == 1)
            parm1 = infoDervFile->infoDervList[recType]->all1DParm[index];
        else /* its 2D */
            parm1 = infoDervFile->infoDervList[recType]->all2DParm[index];

        if (isnan(parm1))
            return (0);

	/* if its an error parmeter, reject it if its assumed or knownbad */
	if (isErrorParm(infoDervFile->infoDervList[recType]->allUsed2DParmList, index))
	{
	    if (parm1 == assumed || parm1 == knownbad)
            return (0);
	}

        /* get parm2 if needed */
        if (infoDervFile->infoDervList[recType]->filt2DList->madfilt_list[filtIndex].filtType != SINGLE_FILT)
        {
            index = infoDervFile->infoDervList[recType]->mapFilt2DParm[4*filtIndex + 3];
            /* find out if its 1D or 2D */
            if (infoDervFile->infoDervList[recType]->mapFilt2DParm[4*filtIndex + 2] == 1)
                parm2 = infoDervFile->infoDervList[recType]->all1DParm[index];
            else /* its 2D */
                parm2 = infoDervFile->infoDervList[recType]->all2DParm[index];

            if (isnan(parm2))
                return (0);

            /* if its an error parmeter, reject it if its assumed or knownbad */
	    if (isErrorParm(infoDervFile->infoDervList[recType]->allUsed2DParmList, index))
	    {
	        if (parm2 == assumed || parm2 == knownbad)
                return (0);
	    }
        }

        /* get filter numRange */
        numRange = infoDervFile->infoDervList[recType]->filt2DList->madfilt_list[filtIndex].numRange;

        /* get filter limits */
        lower = infoDervFile->infoDervList[recType]->filt2DList->madfilt_list[filtIndex].lower;
        upper = infoDervFile->infoDervList[recType]->filt2DList->madfilt_list[filtIndex].upper;

        /* if both missing from all ranges, filter always passes */
        allMissing = 1;
        for (i=0; i<numRange; i++)
        {
            if (!isnan(lower[i]) || !isnan(upper[i]))
            {
                allMissing = 0;
                break;
            }
        }
        if (allMissing) return (1);

        /* switch on filter type */
        switch (infoDervFile->infoDervList[recType]->filt2DList->madfilt_list[filtIndex].filtType)
        {
            case (SINGLE_FILT):
                for (i=0; i<numRange; i++)
                {
                    if (!isnan(lower[i]) && !isnan(upper[i]))
                    {
                        if (lower[i] <= parm1 && parm1 <= upper[i])
                            return(1);
                    }
                    else if (!isnan(lower[i]))
                    {
                        if (lower[i] <= parm1)
                            return(1);
                    }
                    else
                    {
                        if (parm1 <= upper[i])
                            return(1);
                    }
                }
                /* no acceptable range found */
                return(0);
                break;

            case (MULT_FILT):
                for (i=0; i<numRange; i++)
                {
                    if (!isnan(lower[i]) && !isnan(upper[i]))
                    {
                        if (lower[i] <= parm1*parm2 && parm1*parm2 <= upper[i])
                            return(1);
                    }
                    else if (!isnan(lower[i]))
                    {
                        if (lower[i] <= parm1*parm2)
                            return(1);
                    }
                    else
                    {
                        if (parm1*parm2 <= upper[i])
                            return(1);
                    }
                }
                /* no acceptable range found */
                return(0);
                break;

            case (DIV_FILT):
                for (i=0; i<numRange; i++)
                {
                    if (!isnan(lower[i]) && !isnan(upper[i]))
                    {
                        if (lower[i] <= parm1/parm2 && parm1/parm2 <= upper[i])
                            return(1);
                    }
                    else if (!isnan(lower[i]))
                    {
                        if (lower[i] <= parm1/parm2)
                            return(1);
                    }
                    else
                    {
                        if (parm1/parm2 <= upper[i])
                            return(1);
                    }
                }
                /* no acceptable range found */
                return(0);
                break;

            case (ADD_FILT):
                for (i=0; i<numRange; i++)
                {
                    if (!isnan(lower[i]) && !isnan(upper[i]))
                    {
                        if (lower[i] <= parm1+parm2 && parm1+parm2 <= upper[i])
                            return(1);
                    }
                    else if (!isnan(lower[i]))
                    {
                        if (lower[i] <= parm1+parm2)
                            return(1);
                    }
                    else
                    {
                        if (parm1+parm2 <= upper[i])
                            return(1);
                    }
                }
                /* no acceptable range found */
                return(0);
                break;

            case (SUB_FILT):
                for (i=0; i<numRange; i++)
                {
                    if (!isnan(lower[i]) && !isnan(upper[i]))
                    {
                        if (lower[i] <= parm1-parm2 && parm1-parm2 <= upper[i])
                            return(1);
                    }
                    else if (!isnan(lower[i]))
                    {
                        if (lower[i] <= parm1-parm2)
                            return(1);
                    }
                    else
                    {
                        if (parm1-parm2 <= upper[i])
                            return(1);
                    }
                }
                /* no acceptable range found */
                return(0);
                break;

            default:
                /* bug occured */
                assert(0);
        }
    } /* end 2D case */

}


/***********************************************************************
*
* appendMadrecord   appends a new Madrecord to Maddata
*
*   arguments:
*
*      Maddata * maddata - pointer to Maddata to append to
*      InfoDerived * infoDeriv - pointer to InfoDerived that contains the data
*      int cycIndex      - index of cycle to add Madrecord to
*      int typeIndex     - index of type of record. Refers to maddata.madrecParmTypeList
*      Rec_type  rectype - Record type: HEADER_REC, CATALOG_REC, or DATA_REC.  If DATA_REC,
*                          text will be empty string, no matter what passed in. If not,
*                          data1Dparms will be null.
*      char   *  text    - Text of header or catalog record. Empty string if data rec.
*      int  kinst        - instrument id
*      double starttime  - start time of record in seconds since 1/1/1950
*      double endtime    - end time of record in seconds since 1/1/1950
*
*   returns - index of MadRecord added if successful, starting at 0, -1 if error
*/
int appendMadrecord(Maddata * maddata,
                    InfoDerived * infoDerv,
                    int cycIndex,
                    int typeIndex,
                    Rec_type rectype,
                    char * text,
                    int kinst,
                    double starttime,
                    double endtime)
{
    int i = 0;
    Madrecord * madrecord = NULL;

    if (maddata == NULL)
        return (-1);

    /* check that the requested cycle exists */
    assert(maddata->numCycles > cycIndex);

    /* check that the requested type exists */
    assert(maddata->numTypes > typeIndex);

    /* copy the 1D data from all1DParm to tmpOutputParm */
    for (i=0; i<infoDerv->req1DParmList->numParm; i++)
    {
        /* if map = -1, set to missing */
        if (infoDerv->mapReq1DParmList[i] == -1)
            infoDerv->tmpOutputParm[i] = missing;
        else
            infoDerv->tmpOutputParm[i] = infoDerv->all1DParm[infoDerv->mapReq1DParmList[i]];
    }

    maddata->madCycleList[cycIndex]->numMadrecords++;

    /* realloc madRecordList */
    maddata->madCycleList[cycIndex]->madRecordList = (Madrecord **)realloc(maddata->madCycleList[cycIndex]->madRecordList,
                                                      sizeof(Madrecord *)*(maddata->madCycleList[cycIndex]->numMadrecords));
    if (!maddata->madCycleList[cycIndex]->madRecordList)
    {
        perror("realloc");
        exit(-1);
    }

    /* create new madrecord */
    madrecord = createMadrecord(rectype,
                                typeIndex,
                                text,
                                maddata->madrecParmTypeList[typeIndex].parm1DList->numParm,
                                infoDerv->tmpOutputParm,
                                kinst,
                                starttime,
                                endtime);

    maddata->madCycleList[cycIndex]->madRecordList[maddata->madCycleList[cycIndex]->numMadrecords - 1] = madrecord;

    return(maddata->madCycleList[cycIndex]->numMadrecords - 1);
}


/***********************************************************************
*
* updateMadrecordWithMultiRow   modifies an existing Madrecord with data from a multi-row method
*
*   arguments:
*
*      Maddata * maddata - pointer to Maddata to append to
*      InfoMultiRowMethod * infoMultiRowMeth - pointer to InfoMultiRowMethod containing new data
*      int methIndex     - index into which multi-row method this is
*      int cycIndex      - index of cycle that Madrecord is in
*      int recIndex      - index into which record in cycle is being modified
*      int typeIndex     - index of type of record. Refers to maddata.madrecParmTypeList
*      int numRows       - number of 2D rows being updated
*
*   returns - 0 if successful, -1 if error
*/
int updateMadrecordWithMultiRow(Maddata * maddata,
                                InfoMultiRowMethod * infoMultiRowMeth,
                                int methIndex,
                                int cycIndex,
                                int recIndex,
                                int typeIndex,
                                int numRows)
{
    int i = 0;
    int j = 0;
    int index = 0;
    Madrecord * madrecord = NULL;

    if (maddata == NULL)
        return (-1);

    /* check that the requested cycle exists */
    assert(maddata->numCycles > cycIndex);

    /* check that the requested type exists */
    assert(maddata->numTypes > typeIndex);

    /* check that requested record exists */
    assert(maddata->madCycleList[cycIndex]->numMadrecords > recIndex);

    /* point madrecord to Madrecord of interest to shorten code */
    madrecord = maddata->madCycleList[cycIndex]->madRecordList[recIndex];

    /* copy the data from infoMultiRowMeth->outputArr to madrecord */
    for (i=0; i<gCompExtMultiRowList[methIndex].outputCount; i++)
    {
        /* is it a 1D output? */
        if (gCompExtMultiRowList[methIndex].outputMnemType[i] == 1)
        {
            /* get the mnemonic's index */
            index = getIndex(maddata->madrecParmTypeList[typeIndex].parm1DList,
                     gCompExtMultiRowList[methIndex].outputMnemList[i]);

            /* see if this particular output is needed */
            if (index == -1)
                continue;

            /* copy the 1D data */
            madrecord->data1Dparms[index] = infoMultiRowMeth->outputArr[i][0];
        }
        else /* its 2D */
        {
            /* get the mnemonic's index */
            index = getIndex(maddata->madrecParmTypeList[typeIndex].parm2DList,
                     gCompExtMultiRowList[methIndex].outputMnemList[i]);

            /* see if this particular output is needed */
            if (index == -1)
                continue;

            /* copy the 2D data */
            for (j=0; j<numRows; j++)
                madrecord->data2Dparms[j][index] = infoMultiRowMeth->outputArr[i][j];
        }
    }

    return (0);

}


/***********************************************************************
*
* append2DRow   appends a row of 2D data to a Maddata->Madcycle->Madrecord
*
*   arguments:
*
*      Maddata * maddata - pointer to Maddata to append to
*      InfoDerived * infoDeriv - pointer to InfoDerived that contains the data
*      int cycIndex      - index of cycle to add Madrecord to
*      int recIndex      - index of Madrecord in cycle to append 2D
*      int typeIndex     - index of type of record. Refers to maddata.madrecParmTypeList
*
*   returns - index of 2D row added if successful, starting at 0, -1 if error
*/
int append2DRow(Maddata * maddata,
                InfoDerived * infoDerv,
                int cycIndex,
                int typeIndex,
                int recIndex)
{
    int i = 0;
    int num2Dparms = 0; /* holds the number of 2D parameters in the array */
    int num2Drows = 0;  /* holds the new number of 2D rows */

    if (maddata == NULL)
        return (-1);

    /* check that the requested cycle exists */
    assert(maddata->numCycles > cycIndex);

    /* check that the requested Madrecord exists */
    assert(maddata->madCycleList[cycIndex]->numMadrecords > recIndex);

    /* check that the requested type exists */
    assert(maddata->numTypes > typeIndex);

    /* get the number of 2D parameters from madrecParmTypeList */
    num2Dparms = maddata->madrecParmTypeList[typeIndex].parm2DList->numParm;

    /* if no 2d parms requested, no need to add record */
    if (num2Dparms == 0)
        return(0);

    /* check that its a data record */
    if (maddata->madCycleList[cycIndex]->madRecordList[recIndex]->rectype != DATA_REC)
        return (-1);

    /* copy the 2D data from all2DParm to tmpOutputParm */
    for (i=0; i<num2Dparms; i++)
    {
        /* if map = -1, set to missing */
        if (infoDerv->mapReq2DParmList[i] == -1)
            infoDerv->tmpOutputParm[i] = missing;
        else
            infoDerv->tmpOutputParm[i] = infoDerv->all2DParm[infoDerv->mapReq2DParmList[i]];
    }

    maddata->madCycleList[cycIndex]->madRecordList[recIndex]->num2Drows++;

    /* to make the following code more readable and faster, store new num2Drows in local variable */
    num2Drows = maddata->madCycleList[cycIndex]->madRecordList[recIndex]->num2Drows;

    /* realloc data2Dparms to add one more pointer for new data */
    maddata->madCycleList[cycIndex]->madRecordList[recIndex]->data2Dparms = (double **) \
        realloc(maddata->madCycleList[cycIndex]->madRecordList[recIndex]->data2Dparms,
                sizeof(double *)*num2Drows);

    if (!maddata->madCycleList[cycIndex]->madRecordList[recIndex]->data2Dparms)
    {
        perror("realloc");
        exit(-1);
    }

    /* malloc new double array */
    maddata->madCycleList[cycIndex]->madRecordList[recIndex]->data2Dparms[num2Drows-1] = (double *) \
        malloc(sizeof(double)*num2Dparms);

    if (!maddata->madCycleList[cycIndex]->madRecordList[recIndex]->data2Dparms[num2Drows-1])
    {
        perror("malloc");
        exit(-1);
    }

    /* copy input double array */
    for(i=0; i<num2Dparms; i++)
        maddata->madCycleList[cycIndex]->madRecordList[recIndex]->data2Dparms[num2Drows-1][i] = infoDerv->tmpOutputParm[i];

    return(0);
}



/***********************************************************************
*
* createInfoDerived - sets up a InfoDerived struct in preparation for
*                     calculating all derived parameters for a given
*                     record type
*
*   A record type is a unique ordered combination of 1d measured parameters and
*   2d measured parameters
*
*   arguments:
*      MadparmList * meas1DParmList - list of measured 1D parameters
*      MadparmList * meas2DParmList - list of measured 2D parameters
*      MadparmList * requestedParmList - list of parameters requested
*      MadfilterList * filtList - list of filters requested
*
*   Searchs through the information in gCompExtList to determine which
*   methods need to be called for 1D and 2D cases.  Determines which
*   requested parameters can not be derived.  Sets up allocated memory
*   to hold all measured and derived parameters. Sets up inputMap and
*   outputMap to rapidly move data into input and output arrays required
*   for each method.  Free using destroyInfoDerived.
*
*   returns - pointer to created InfoDerived struct; if failure,
*             returns NULL
*/
InfoDerived * createInfoDerived(MadparmList * meas1DParmList,
                                MadparmList * meas2DParmList,
                                MadparmList * requestedParmList,
                                MadfilterList * filtList)
{
    InfoDerived * newInfoDeriv = NULL;  /* pointer to data structure to be returned */
    int numDervMeth = 0;                /* total number of registered derived methods */
    int numMultiRowMeth = 0;            /* total number of registered derived multi-row methods */
    int i = 0;                          /* loop variables */
    int j = 0;
    int k = 0;
    int index = 0;
    int num1DFilt = 0;
    int num2DFilt = 0;
    int num1DMeasParm = 0;
    int num2DMeasParm = 0;
    MadparmList * foundOutputList = NULL;  /* used to keep track of which output parameters have already been found */
    MadparmList * filtParmsNotRequestedList = NULL; /* a list of filter parameters not in requestedParmList */
                                                    /* These must also be determined if possible            */

    /* state variables */
    int inputParmFound = 0;
    int method1DOkay   = 0;
    int method2DOkay   = 0;

    /* count number of derived methods by looking for last NULL */
    while (gCompExtList[i].compExt != NULL)
        i++;

    numDervMeth = i;

    /* count number of derived multi-row methods by looking for last NULL */
    i = 0;
    while (gCompExtMultiRowList[i].compExt != NULL)
        i++;

    numMultiRowMeth = i;

    /* malloc newInfoDeriv */
    if ((newInfoDeriv = (InfoDerived *)malloc(sizeof(InfoDerived)))==0)
    {
        perror("malloc");
        exit(-1);
    }

    /* initialize to 0 */
    memset(newInfoDeriv, 0, sizeof(InfoDerived));

    /* malloc newInfoDeriv->infoMethodArr */
    if ((newInfoDeriv->infoMethodArr = (InfoMethod **)malloc(sizeof(InfoMethod *) * numDervMeth))==0)
    {
        perror("malloc");
        exit(-1);
    }

    /* now create each InfoMethod in newInfoDeriv->infoMethodArr */
    for (i=0; i<numDervMeth; i++)
    {
        newInfoDeriv->infoMethodArr[i] = createInfoMethod(gCompExtList[i].inputCount,
                                                          gCompExtList[i].outputCount);
    }

    newInfoDeriv->numDervMeth = numDervMeth;

    /* malloc newInfoDeriv->infoMultiRowMethArr */
    if ((newInfoDeriv->infoMultiRowMethArr = (InfoMultiRowMethod **)malloc(sizeof(InfoMultiRowMethod *) * numMultiRowMeth))==0)
    {
        perror("malloc");
        exit(-1);
    }

    /* now create each InfoMultiRowMethod in newInfoDeriv->infoMultiRowMethArr */
    for (i=0; i<numMultiRowMeth; i++)
    {
        newInfoDeriv->infoMultiRowMethArr[i] = createInfoMultiRowMethod(gCompExtMultiRowList[i].inputCount,
                                                                        gCompExtMultiRowList[i].inputMnemType,
                                                                        gCompExtMultiRowList[i].outputCount,
                                                                        gCompExtMultiRowList[i].outputMnemType);
    }

    newInfoDeriv->numMultiRowMeth = numMultiRowMeth;

    /* copy three input MadparmLists into newInfoDeriv */
    newInfoDeriv->meas1DParmList = copyMadparmList(meas1DParmList);
    newInfoDeriv->meas2DParmList = copyMadparmList(meas2DParmList);
    newInfoDeriv->requestedParmList = copyMadparmList(requestedParmList);

    /* allocate memory for meas1DCodeList member */
    num1DMeasParm = newInfoDeriv->meas1DParmList->numParm - NUM_PROLOG_PARM;
    newInfoDeriv->meas1DCodeList = (int *)malloc(sizeof(int)*num1DMeasParm);
    if (!newInfoDeriv->meas1DCodeList)
    {
        perror("malloc");
        exit(-1);
    }
    for (i=0; i<num1DMeasParm; i++)
    {
        newInfoDeriv->meas1DCodeList[i] = cedarGetParCodeFromMnemonic(newInfoDeriv->meas1DParmList->mnemList[i+NUM_PROLOG_PARM]);
        /* if parameter code not found, bug in code */
        assert(newInfoDeriv->meas1DCodeList[i] != missingData);
    }

    /* allocate memory for meas2DCodeList member */
    num2DMeasParm = newInfoDeriv->meas2DParmList->numParm - NUM_2D_PROLOG_PARM;
    newInfoDeriv->meas2DCodeList = (int *)malloc(sizeof(int)*num2DMeasParm);
    if (!newInfoDeriv->meas2DCodeList)
    {
        perror("malloc");
        exit(-1);
    }
    for (i=0; i<num2DMeasParm; i++)
    {
        newInfoDeriv->meas2DCodeList[i] = cedarGetParCodeFromMnemonic(newInfoDeriv->meas2DParmList->mnemList[i+NUM_2D_PROLOG_PARM]);
        /* if parameter code not found, bug in code */
        assert(newInfoDeriv->meas2DCodeList[i] != missingData);
    }

    /* create empty unavailParmList, allUsed1DParmList, allAvail1DParmList, allUsed2DParmList, */
    /* allAvail2DParmList, req1DParmList, and req2DParmList                                    */
    /* these will be populated during analysis                                                 */
    newInfoDeriv->unavailParmList = createMadparmList();
    newInfoDeriv->allUsed1DParmList = createMadparmList();
    newInfoDeriv->allAvail1DParmList = createMadparmList();
    newInfoDeriv->allUsed2DParmList = createMadparmList();
    newInfoDeriv->allAvail2DParmList = createMadparmList();
    newInfoDeriv->req1DParmList = createMadparmList();
    newInfoDeriv->req2DParmList = createMadparmList();

    /* create empty filt1DList, filt2DList, mapReq1DParmList, mapReq2DParmList */
    /* these will be populated during analysis                                 */
    newInfoDeriv->filt1DList = createMadfilterList();
    newInfoDeriv->filt2DList = createMadfilterList();
    newInfoDeriv->mapReq1DParmList = NULL;
    newInfoDeriv->mapReq2DParmList = NULL;

    /* find out what parameters are used in filters that have not been requested */
    filtParmsNotRequestedList = createMadparmList();
    for (i=0; i<filtList->numFilters; i++)
    {
        if (!hasParm(requestedParmList, filtList->madfilt_list[i].madParm1))
            appendMadparm(filtParmsNotRequestedList, filtList->madfilt_list[i].madParm1);

        /* make sure filter has a second parameter */
        if (filtList->madfilt_list[i].filtType != SINGLE_FILT)
        {
            if (!hasParm(requestedParmList, filtList->madfilt_list[i].madParm2))
                appendMadparm(filtParmsNotRequestedList, filtList->madfilt_list[i].madParm2);
        }
    }


    /* add all meas 1D parameters that were requested directly to                */
    /* allUsed1DParmList since they won't need to be derived                     */

    for(i=0; i < newInfoDeriv->meas1DParmList->numParm; i++)
    {
        appendMadparm(newInfoDeriv->allUsed1DParmList, newInfoDeriv->meas1DParmList->mnemList[i]);
        appendMadparm(newInfoDeriv->allAvail1DParmList, newInfoDeriv->meas1DParmList->mnemList[i]);
    }


    /* add all meas 2D parameters that were requested directly to                */
    /* allUsed2DParmList since they won't need to be derived                     */
    for(i=0; i < newInfoDeriv->meas2DParmList->numParm; i++)
    {
        appendMadparm(newInfoDeriv->allUsed2DParmList, newInfoDeriv->meas2DParmList->mnemList[i]);
        appendMadparm(newInfoDeriv->allAvail2DParmList, newInfoDeriv->meas2DParmList->mnemList[i]);
    }

    /* loop through all derived methods                                          */
    /* in this loop i = index of method being analyzed                           */
    /*              j = index of input parameter of method being analyzed        */
    /*              k = index of preceding methods that may supply input (k < i) */
    /*              (Maddata always assumes all inputs come from measured data   */
    /*               or preceding methods - never from later methods)            */
    for (i=0; i<numDervMeth; i++)
    {
        /* first we check to see if this is a valid 1D method */
        method1DOkay = 1;
        /* loop through each input in this method to see if its available as 1D */
        for (j=0; j < gCompExtList[i].inputCount; j++)
        {
            inputParmFound = 0;
            /* first check if its a meas 1D parameter */
            if (hasParm(newInfoDeriv->meas1DParmList, gCompExtList[i].inputMnemList[j]))
                continue;
            /* if its a 2D parameter, method1DOkay = 0 */
            if (hasParm(newInfoDeriv->allAvail2DParmList, gCompExtList[i].inputMnemList[j]))
            {
                method1DOkay = 0;
                /* no need to examine any more input parameters */
                break;
            }
            /* not measured 1D - see if a previous method derived it */
            /* loop through all previously checked methods */
            for (k=0; k<i; k++)
            {
                /* skip methods that don't give 1D outputs */
                if (!newInfoDeriv->infoMethodArr[k]->all1D)
                    continue;
                /* check if this method gives the parameter we need */
                /* if so, update numInputMethods and neededMethods  */
                if (hasOutput(gCompExtList + k, gCompExtList[i].inputMnemList[j]))
                {
                    /* this method depends on earlier method k */
                    newInfoDeriv->infoMethodArr[i]->neededMethods[newInfoDeriv->infoMethodArr[i]->numInputMethods] = k;
                    newInfoDeriv->infoMethodArr[i]->numInputMethods++;
                    inputParmFound = 1;
                    break;
                }
            } /* next previous derived method (k) */

            /* check whether input parameter was found in above loop  */
            /* if not, meth not available for 1D calculations */
            if (!inputParmFound)
            {
                method1DOkay = 0;
                /* no need to examine any more input parameters */
                break;
            }

        } /* next input parameter (j) */

        /* all input parameters checked - check if method1DOkay */
        if (method1DOkay)
        {
            newInfoDeriv->infoMethodArr[i]->all1D = 1;
            newInfoDeriv->infoMethodArr[i]->isAvailable = 1;

            /* mark all its output parameters as available */
            for (j=0; j<gCompExtList[i].outputCount; j++)
            {
                if (!hasParm(newInfoDeriv->allAvail1DParmList, gCompExtList[i].outputMnemList[j]) &&
                    !hasParm(newInfoDeriv->allAvail2DParmList, gCompExtList[i].outputMnemList[j]))
                    appendMadparm(newInfoDeriv->allAvail1DParmList, gCompExtList[i].outputMnemList[j]);
            }

            /* now check if any output parameters are in requestedParmList or filtParmsNotRequestedList */
            /* if so, mark all preceding required methods as needed */
            checkIf1DMethodNeeded(newInfoDeriv, i, filtParmsNotRequestedList);
            continue;
        }
        else
        {
            newInfoDeriv->infoMethodArr[i]->all1D = 0;
        }

        /* Was not a possible 1D method - check it as a 2D method */

        method2DOkay = 1;

        /* if its already been found as a 1D method, skip it */
        if (newInfoDeriv->infoMethodArr[i]->all1D == 1)
            continue;

        /* loop through each input in this method to see if its available */
        for (j=0; j < gCompExtList[i].inputCount; j++)
        {
            inputParmFound = 0;
            /* first check if its a meas 2D parameter */
            if (hasParm(newInfoDeriv->meas2DParmList, gCompExtList[i].inputMnemList[j]))
                continue;
            /* next check if its already available from 1D calculations */
            if (hasParm(newInfoDeriv->allUsed1DParmList, gCompExtList[i].inputMnemList[j]))
                continue;
            /* next check if its already available from 2D calculations */
            if (hasParm(newInfoDeriv->allUsed2DParmList, gCompExtList[i].inputMnemList[j]))
                continue;
            /* next see if a previous 2D method derived it */
            /* loop through all previously checked methods */
            for (k=0; k<i; k++)
            {
                /* skip 1D methods */
                if (newInfoDeriv->infoMethodArr[k]->all1D)
                    continue;
                /* skip unavailable methods */
                if (!newInfoDeriv->infoMethodArr[k]->isAvailable)
                    continue;
                /* check if this method gives the parameter we need */
                /* if so, update numInputMethods and neededMethods  */
                if (hasOutput(gCompExtList + k, gCompExtList[i].inputMnemList[j]))
                {
                    /* this methods depends on earlier method k */
                    newInfoDeriv->infoMethodArr[i]->neededMethods[newInfoDeriv->infoMethodArr[i]->numInputMethods] = k;
                    newInfoDeriv->infoMethodArr[i]->numInputMethods++;
                    inputParmFound = 1;
                    break;
                }
            } /* next previous derived method (k) */
            /* finally check if an available 1D method can derive it, but not yet marked needed */
            if (hasParm(newInfoDeriv->allAvail1DParmList, gCompExtList[i].inputMnemList[j]))
            {
               /* mark that 1D method as needed when you find which one it is */
               /* only need to look at preceding methods, so stop at method i */
               for (k=0; k<i; k++)
               {
                   if (!newInfoDeriv->infoMethodArr[k]->all1D)
                       continue;
                   if (!newInfoDeriv->infoMethodArr[k]->isAvailable)
                       continue;
                   /* shouldn't already be needed yet */
                   if (newInfoDeriv->infoMethodArr[k]->isNeeded)
                       continue;
                   if (hasOutput(gCompExtList + k, gCompExtList[i].inputMnemList[j]))
                   {
                       /* right 1D method found */
                       make1DMethodNeeded(newInfoDeriv, k);
                       break;
                   }
               }
               inputParmFound = 1;
            }

            /* check whether input parameter was found   */
            /* if not, meth not available for 2D calculations */
            if (!inputParmFound)
            {
                method2DOkay = 0;
                /* no need to examine any more input parameters */
                break;
            }

        } /* next input parameter (j) */

        /* all input parameters checked - check if method2DOkay */
        if (method2DOkay)
        {
            newInfoDeriv->infoMethodArr[i]->all1D = 0;
            newInfoDeriv->infoMethodArr[i]->isAvailable = 1;

            /* mark all its output parameters as available */
            for (j=0; j<gCompExtList[i].outputCount; j++)
            {
                if (!hasParm(newInfoDeriv->allAvail1DParmList, gCompExtList[i].outputMnemList[j]) &&
                    !hasParm(newInfoDeriv->allAvail2DParmList, gCompExtList[i].outputMnemList[j]))
                    appendMadparm(newInfoDeriv->allAvail2DParmList, gCompExtList[i].outputMnemList[j]);
            }

            /* now check if any output parameters are in requestedParmList or filtParmsNotRequestedList*/
            /* if so, mark all preceding required methods as needed */
            checkIf2DMethodNeeded(newInfoDeriv, i, filtParmsNotRequestedList);
        }
        else
            newInfoDeriv->infoMethodArr[i]->isAvailable = 0;

    } /* next derived method (i) */


    /* now loop through all derived multi-row methods to see if they're needed   */
    /* in this loop i = index of method being analyzed                           */
    /*              j = index of input parameter of method being analyzed        */
    for (i=0; i<numMultiRowMeth; i++)
    {
        /* assume this multi-row method is needed until proved otherwise */
        newInfoDeriv->infoMultiRowMethArr[i]->isNeeded = 1;

        /* loop through each input parameter */
        for (j=0; j < gCompExtMultiRowList[i].inputCount; j++)
        {

            assert (gCompExtMultiRowList[i].inputMnemType[j] == 1 ||
                    gCompExtMultiRowList[i].inputMnemType[j] == 2);

            /* check if its a 1D input */
            if (gCompExtMultiRowList[i].inputMnemType[j] == 1)
            {
                /* see if its available at all */
                if (!hasParm(newInfoDeriv->allAvail1DParmList, gCompExtMultiRowList[i].inputMnemList[j]))
                {
                    newInfoDeriv->infoMultiRowMethArr[i]->isNeeded = 0;
                    break;
                }
                /* now see if its already being calculated */
                if (!hasParm(newInfoDeriv->allUsed1DParmList, gCompExtMultiRowList[i].inputMnemList[j]))
                {
                    /* we need to make this parameter used */
                    /* mark that 1D method as needed when you find which one it is */
                    for (k=0; k<numDervMeth; k++)
                    {
                       if (!newInfoDeriv->infoMethodArr[k]->all1D)
                           continue;
                       if (!newInfoDeriv->infoMethodArr[k]->isAvailable)
                           continue;
                       /* shouldn't already be needed yet */
                       if (newInfoDeriv->infoMethodArr[k]->isNeeded)
                           continue;
                       if (hasOutput(gCompExtList + k, gCompExtList[i].inputMnemList[j]))
                       {
                           /* right 1D method found */
                           make1DMethodNeeded(newInfoDeriv, k);
                           break;
                       }
                    } /* try next method */
                }
            }

            else /* its a 2D input */
            {
                /* see if its available at all */
                if (!hasParm(newInfoDeriv->allAvail2DParmList, gCompExtMultiRowList[i].inputMnemList[j]))
                {
                    newInfoDeriv->infoMultiRowMethArr[i]->isNeeded = 0;
                    break;
                }
                /* now see if its already being calculated */
                if (!hasParm(newInfoDeriv->allUsed2DParmList, gCompExtMultiRowList[i].inputMnemList[j]))
                {
                    /* we need to make this parameter used */
                    /* mark that 2D method as needed when you find which one it is */
                    for (k=0; k<numDervMeth; k++)
                    {
                       if (newInfoDeriv->infoMethodArr[k]->all1D)
                           continue;
                       if (!newInfoDeriv->infoMethodArr[k]->isAvailable)
                           continue;
                       /* shouldn't already be needed yet */
                       if (newInfoDeriv->infoMethodArr[k]->isNeeded)
                           continue;
                       if (hasOutput(gCompExtList + k, gCompExtList[i].inputMnemList[j]))
                       {
                           /* right 2D method found */
                           make2DMethodNeeded(newInfoDeriv, k);
                           break;
                       }
                    } /* try next method */
                }

            }
        } /* next input mnemonic */

        if (newInfoDeriv->infoMultiRowMethArr[i]->isNeeded == 0)
            break;

        /* now that we know the multi-row method is available, see if its needed */
        checkIfMultiRowMethodNeeded(newInfoDeriv, i);
    }

    /* now that all methods have been analyzed, populate inputMap and outputMap for each method */
    /* to allow rapid dispatch of each method.  These maps are used to copy data from all1DParm */
    /* and all2DParm into each method's input array, and then from the output array back into   */
    /* all1DParm and all2DParm.                                                                 */

    foundOutputList = createMadparmList();

    for (i=0; i<numDervMeth; i++)
    {
        /* if method isn't needed, skip it */
        if (!newInfoDeriv->infoMethodArr[i]->isNeeded)
        {
            continue;
        }

        /* first handle 1D methods */
        if (newInfoDeriv->infoMethodArr[i]->all1D)
        {
            /* loop through each input parameter */
            for (j=0; j < gCompExtList[i].inputCount; j++)
            {
                index = getIndex(newInfoDeriv->allUsed1DParmList, gCompExtList[i].inputMnemList[j]);
                /* if index == -1, there's a bug in the code ! */
                assert(index + 1);
                /* mark as 1D input  and index in inputMap */
                newInfoDeriv->infoMethodArr[i]->inputMap[j*2] = 1;
                newInfoDeriv->infoMethodArr[i]->inputMap[j*2 + 1] = index;
            }
            /* loop through each output parameter */
            for (j=0; j < gCompExtList[i].outputCount; j++)
            {
                /* if its a measured 1D parameter, ignore it */
                if (hasParm(newInfoDeriv->meas1DParmList, gCompExtList[i].outputMnemList[j]))
                {
                    newInfoDeriv->infoMethodArr[i]->outputMap[j] = -1;
                    continue;
                }

                /* if its a measured 2D parameter, ignore it */
                if (hasParm(newInfoDeriv->meas2DParmList, gCompExtList[i].outputMnemList[j]))
                {
                    newInfoDeriv->infoMethodArr[i]->outputMap[j] = -1;
                    continue;
                }

                /* if its already been calculated earlier, ignore it */
                if (hasParm(foundOutputList, gCompExtList[i].outputMnemList[j]))
                {
                    newInfoDeriv->infoMethodArr[i]->outputMap[j] = -1;
                    continue;
                }

                /* this is the first method to calculate it, so add it to foundOutputList */
                index = appendMadparm(foundOutputList, gCompExtList[i].outputMnemList[j]);
                if (index == -1)
                {
                    printf("Illegal parameter %s in gCompExtList!", gCompExtList[i].outputMnemList[j]);
                    exit(-1);
                }

                index = getIndex(newInfoDeriv->allUsed1DParmList, gCompExtList[i].outputMnemList[j]);

                /* if index == -1, there's a bug in the code ! */
                assert(index + 1);

                /* add index to outputMap */
                newInfoDeriv->infoMethodArr[i]->outputMap[j] = index;
            }
        }

        /* now handle 2D methods */
        else
        {
            /* loop through each input parameter */
            for (j=0; j < gCompExtList[i].inputCount; j++)
            {
                index = getIndex(newInfoDeriv->allUsed1DParmList, gCompExtList[i].inputMnemList[j]);
                /* if index == -1, must be 2D input */
                if (index == -1)
                {
                    index = getIndex(newInfoDeriv->allUsed2DParmList, gCompExtList[i].inputMnemList[j]);
                    /* if index still == -1, there's a bug in the code ! */
                    assert(index + 1);
                    /* mark as 2D input */
                    newInfoDeriv->infoMethodArr[i]->inputMap[j*2] = 2;
                }
                else  /* its a 1D input */
                    newInfoDeriv->infoMethodArr[i]->inputMap[j*2] = 1;

                newInfoDeriv->infoMethodArr[i]->inputMap[j*2 + 1] = index;
            }
            /* loop through each output parameter */
            for (j=0; j < gCompExtList[i].outputCount; j++)
            {
                /* if its a measured 1D parameter, ignore it */
                if (hasParm(newInfoDeriv->meas1DParmList, gCompExtList[i].outputMnemList[j]))
                {
                    newInfoDeriv->infoMethodArr[i]->outputMap[j] = -1;
                    continue;
                }

                /* if its a measured 2D parameter, ignore it */
                if (hasParm(newInfoDeriv->meas2DParmList, gCompExtList[i].outputMnemList[j]))
                {
                    newInfoDeriv->infoMethodArr[i]->outputMap[j] = -1;
                    continue;
                }

                /* if its already been calculated earlier, ignore it */
                if (hasParm(foundOutputList, gCompExtList[i].outputMnemList[j]))
                {
                    newInfoDeriv->infoMethodArr[i]->outputMap[j] = -1;
                    continue;
                }

                /* this is the first method to calculate it, so add it to foundOutputList */
                index = appendMadparm(foundOutputList, gCompExtList[i].outputMnemList[j]);
                if (index == -1)
                {
                    printf("Illegal parameter %s in gCompExtList!", gCompExtList[i].outputMnemList[j]);
                    exit(-1);
                }

                /* this is a 2D method, so its outputs go into allUsed2DParmList only */
                index = getIndex(newInfoDeriv->allUsed2DParmList, gCompExtList[i].outputMnemList[j]);

                /* if index == -1, it may already be available as 1D, so ignore ! */

                /* add index to outputMap */
                newInfoDeriv->infoMethodArr[i]->outputMap[j] = index;

            }/* end loop through each 2Doutput parameter */

        } /* end handling 2D Methods */

    } /* next method */

    /* now find the requested parameters that are unavailable, 1D and 2D */
    for (i=0; i<requestedParmList->numParm; i++)
    {
        if (hasParm(newInfoDeriv->allUsed1DParmList, requestedParmList->mnemList[i]))
            appendMadparm(newInfoDeriv->req1DParmList, requestedParmList->mnemList[i]);

        else if (hasParm(newInfoDeriv->allUsed2DParmList, requestedParmList->mnemList[i]))
            appendMadparm(newInfoDeriv->req2DParmList, requestedParmList->mnemList[i]);

        else /* parameter was not able to be derived */
        {
            appendMadparm(newInfoDeriv->unavailParmList, requestedParmList->mnemList[i]);
            /* add it to the 1D list (no sense wasting too much memory on it) */
            appendMadparm(newInfoDeriv->req1DParmList, requestedParmList->mnemList[i]);
        }
    }


    /* now create mapReq1DParmList and mapReq2DParmList that map the required outputs   */
    /* into allUsed1DParmList and allUsed2DParmList so output can be rapidly copied out */

    /* mapReq1DParmList  */
    newInfoDeriv->mapReq1DParmList = (int *)malloc(sizeof(int) * newInfoDeriv->req1DParmList->numParm);
    if (!newInfoDeriv->mapReq1DParmList)
    {
        perror("malloc");
        exit(-1);
    }

    for (i=0; i<newInfoDeriv->req1DParmList->numParm; i++)
    {
        /* note that getIndex returns -1 if parameter not in list, as needed */
        newInfoDeriv->mapReq1DParmList[i] = getIndex(newInfoDeriv->allUsed1DParmList,
                                                  newInfoDeriv->req1DParmList->mnemList[i]);
    }

    /* mapReq2DParmList  */
    newInfoDeriv->mapReq2DParmList = (int *)malloc(sizeof(int) * newInfoDeriv->req2DParmList->numParm);
    if (!newInfoDeriv->mapReq2DParmList)
    {
        perror("malloc");
        exit(-1);
    }

    for (i=0; i<newInfoDeriv->req2DParmList->numParm; i++)
    {
        newInfoDeriv->mapReq2DParmList[i] = getIndex(newInfoDeriv->allUsed2DParmList,
                                                  newInfoDeriv->req2DParmList->mnemList[i]);
    }


    /* now populate filter lists, adding each to 1D or 2D filter list */
    newInfoDeriv->validFilters = 1;  /* assume all filters valid until proved otherwise */

    /* these members keep track of whether filters use only measured parameters */
    newInfoDeriv->onlyMeas1DList = NULL;
    newInfoDeriv->onlyMeas2DList = NULL;

    for (i=0; i<filtList->numFilters; i++)
    {
        if (filtList->madfilt_list[i].filtType == SINGLE_FILT)
        {
            /* is it 1D */
            if (hasParm(newInfoDeriv->allUsed1DParmList, filtList->madfilt_list[i].madParm1))
            {
                num1DFilt++;
                appendMadfilter(newInfoDeriv->filt1DList,
                                filtList->madfilt_list[i].filtType,
                                filtList->madfilt_list[i].numRange,
                                filtList->madfilt_list[i].lower,
                                filtList->madfilt_list[i].upper,
                                filtList->madfilt_list[i].madParm1,
                                filtList->madfilt_list[i].madParm2);

                newInfoDeriv->onlyMeas1DList = (int *)realloc(newInfoDeriv->onlyMeas1DList, sizeof(int)*num1DFilt);
                if (!newInfoDeriv->onlyMeas1DList)
                {
                    perror("malloc");
                    exit(-1);
                }
                /* does this 1D filter only use measured parameters ? */
                if (hasParm(newInfoDeriv->meas1DParmList, filtList->madfilt_list[i].madParm1))
                    newInfoDeriv->onlyMeas1DList[num1DFilt-1] = 1;
                else
                    newInfoDeriv->onlyMeas1DList[num1DFilt-1] = 0;
            }
            /* is it 2D  */
            else if (hasParm(newInfoDeriv->allUsed2DParmList, filtList->madfilt_list[i].madParm1))
            {
                num2DFilt++;
                appendMadfilter(newInfoDeriv->filt2DList,
                                filtList->madfilt_list[i].filtType,
                                filtList->madfilt_list[i].numRange,
                                filtList->madfilt_list[i].lower,
                                filtList->madfilt_list[i].upper,
                                filtList->madfilt_list[i].madParm1,
                                filtList->madfilt_list[i].madParm2);

                newInfoDeriv->onlyMeas2DList = (int *)realloc(newInfoDeriv->onlyMeas2DList, sizeof(int)*num2DFilt);
                if (!newInfoDeriv->onlyMeas2DList)
                {
                    perror("malloc");
                    exit(-1);
                }
                /* does this 2D filter only use measured parameters ? */
                if (hasParm(newInfoDeriv->meas2DParmList, filtList->madfilt_list[i].madParm1))
                    newInfoDeriv->onlyMeas2DList[num2DFilt-1] = 1;
                else
                    newInfoDeriv->onlyMeas2DList[num2DFilt-1] = 0;
            }
            else   /* filter unable to be calculated - this record type always rejected */
                newInfoDeriv->validFilters = 0;
        }
        else  /* filter uses two parameters */
        {
            /* is it 1D */
            if (hasParm(newInfoDeriv->allUsed1DParmList, filtList->madfilt_list[i].madParm1) &&
                hasParm(newInfoDeriv->allUsed1DParmList, filtList->madfilt_list[i].madParm2))
            {
                num1DFilt++;
                appendMadfilter(newInfoDeriv->filt1DList,
                                filtList->madfilt_list[i].filtType,
                                filtList->madfilt_list[i].numRange,
                                filtList->madfilt_list[i].lower,
                                filtList->madfilt_list[i].upper,
                                filtList->madfilt_list[i].madParm1,
                                filtList->madfilt_list[i].madParm2);

                newInfoDeriv->onlyMeas1DList = (int *)realloc(newInfoDeriv->onlyMeas1DList, sizeof(int)*num1DFilt);
                if (!newInfoDeriv->onlyMeas1DList)
                {
                    perror("malloc");
                    exit(-1);
                }
                /* does this 1D filter only use measured parameters ? */
                if (hasParm(newInfoDeriv->meas1DParmList, filtList->madfilt_list[i].madParm1) &&
                    hasParm(newInfoDeriv->meas1DParmList, filtList->madfilt_list[i].madParm2))
                    newInfoDeriv->onlyMeas1DList[num1DFilt-1] = 1;
                else
                    newInfoDeriv->onlyMeas1DList[num1DFilt-1] = 0;
            }

            /* is it 2D (or 1D and 2D together) */
            else if ((hasParm(newInfoDeriv->allUsed1DParmList, filtList->madfilt_list[i].madParm1) ||
                      hasParm(newInfoDeriv->allUsed2DParmList, filtList->madfilt_list[i].madParm1)) &&
                     (hasParm(newInfoDeriv->allUsed1DParmList, filtList->madfilt_list[i].madParm2) ||
                      hasParm(newInfoDeriv->allUsed2DParmList, filtList->madfilt_list[i].madParm2)))
            {
                num2DFilt++;
                appendMadfilter(newInfoDeriv->filt2DList,
                                filtList->madfilt_list[i].filtType,
                                filtList->madfilt_list[i].numRange,
                                filtList->madfilt_list[i].lower,
                                filtList->madfilt_list[i].upper,
                                filtList->madfilt_list[i].madParm1,
                                filtList->madfilt_list[i].madParm2);

                newInfoDeriv->onlyMeas2DList = (int *)realloc(newInfoDeriv->onlyMeas2DList, sizeof(int)*num2DFilt);
                if (!newInfoDeriv->onlyMeas2DList)
                {
                    perror("malloc");
                    exit(-1);
                }
                /* does this 2D filter only use 2D measured parameters and 1D parameters ? */
                if ((hasParm(newInfoDeriv->meas2DParmList, filtList->madfilt_list[i].madParm1) ||
                     hasParm(newInfoDeriv->allUsed1DParmList, filtList->madfilt_list[i].madParm1)) &&
                    (hasParm(newInfoDeriv->meas2DParmList, filtList->madfilt_list[i].madParm2) ||
                     hasParm(newInfoDeriv->allUsed1DParmList, filtList->madfilt_list[i].madParm2)))
                    newInfoDeriv->onlyMeas2DList[num2DFilt-1] = 1;
                else
                    newInfoDeriv->onlyMeas2DList[num2DFilt-1] = 0;
            }
            else   /* filter unable to be calculated - this record type always rejected */
                newInfoDeriv->validFilters = 0;
        }
    }  /* next filter */

    /* now that filt1DList and filt2DList have been determined, set up mapFilt1DParm and mapFilt2DParm */
    /* that allow rapid copying of data into evaluateFilter routine                                    */

    /* first set up  mapFilt1DParm - 2 ints per filter (one for each parameter) */
    if ((newInfoDeriv->mapFilt1DParm = (int *)malloc(sizeof(int)*2*newInfoDeriv->filt1DList->numFilters))==0)
    {
        perror("malloc");
        exit(-1);
    }
    for (i=0; i<newInfoDeriv->filt1DList->numFilters; i++)
    {
        newInfoDeriv->mapFilt1DParm[2*i] = getIndex(newInfoDeriv->allUsed1DParmList,
                                                    newInfoDeriv->filt1DList->madfilt_list[i].madParm1);
        /* check if this filter has a second parameter */
        if (newInfoDeriv->filt1DList->madfilt_list[i].filtType == SINGLE_FILT)
            newInfoDeriv->mapFilt1DParm[2*i + 1] = -1;
        else
           newInfoDeriv->mapFilt1DParm[2*i + 1] = getIndex(newInfoDeriv->allUsed1DParmList,
                                                           newInfoDeriv->filt1DList->madfilt_list[i].madParm2);
    }

    /* next set up  mapFilt2DParm - 4 ints per filter - 1: 1 or 2 D, 1st parm,           */
    /* 2: index of 1st parm, 3: 1 or 2 D, 2nd parm (or -1), 4: index of 2nd parm (or -1) */
    if ((newInfoDeriv->mapFilt2DParm = (int *)malloc(sizeof(int)*4*newInfoDeriv->filt2DList->numFilters))==0)
    {
        perror("malloc");
        exit(-1);
    }
    for (i=0; i<newInfoDeriv->filt2DList->numFilters; i++)
    {
        /* see if 1st parm is 1D or 2D */
        index = getIndex(newInfoDeriv->allUsed1DParmList, newInfoDeriv->filt2DList->madfilt_list[i].madParm1);
        if (index != -1)
        {
            newInfoDeriv->mapFilt2DParm[4*i] = 1; /* its 1D */
            newInfoDeriv->mapFilt2DParm[4*i + 1] = index;
        }
        else
        {
            newInfoDeriv->mapFilt2DParm[4*i] = 2; /* its 2D */
            newInfoDeriv->mapFilt2DParm[4*i + 1] = getIndex(newInfoDeriv->allUsed2DParmList,
                                                            newInfoDeriv->filt2DList->madfilt_list[i].madParm1);
        }

        /* check if this filter has a second parameter */
        if (newInfoDeriv->filt2DList->madfilt_list[i].filtType == SINGLE_FILT)
        {
            newInfoDeriv->mapFilt2DParm[4*i + 2] = -1;
            newInfoDeriv->mapFilt2DParm[4*i + 3] = -1;
        }
        else
        {
            index = getIndex(newInfoDeriv->allUsed1DParmList, newInfoDeriv->filt2DList->madfilt_list[i].madParm2);
            if (index != -1)
            {
                newInfoDeriv->mapFilt2DParm[4*i + 2] = 1; /* its 1D */
                newInfoDeriv->mapFilt2DParm[4*i + 3] = index;
            }
            else
            {
                newInfoDeriv->mapFilt2DParm[4*i + 2] = 2; /* its 2D */
                newInfoDeriv->mapFilt2DParm[4*i + 3] = getIndex(newInfoDeriv->allUsed2DParmList,
                                                                newInfoDeriv->filt2DList->madfilt_list[i].madParm2);
            }
        }
    }

    /* finally, allocate memory for calculated values during analysis */
    if ((newInfoDeriv->all1DParm = (double *)malloc(sizeof(double)*newInfoDeriv->allUsed1DParmList->numParm))==0)
    {
        perror("malloc");
        exit(-1);
    }
    if ((newInfoDeriv->all2DParm = (double *)malloc(sizeof(double)*newInfoDeriv->allUsed2DParmList->numParm))==0)
    {
        perror("malloc");
        exit(-1);
    }
    if ((newInfoDeriv->tmpInputParm = (double *)malloc((sizeof(double)*newInfoDeriv->unavailParmList->numParm) + \
													   (sizeof(double)*newInfoDeriv->allUsed1DParmList->numParm) + \
													   (sizeof(double)*newInfoDeriv->allUsed2DParmList->numParm)))==0)
	{
		perror("malloc");
		exit(-1);
	}
	if ((newInfoDeriv->tmpOutputParm = (double *)malloc((sizeof(double)*newInfoDeriv->unavailParmList->numParm) + \
														(sizeof(double)*newInfoDeriv->allUsed1DParmList->numParm) + \
														(sizeof(double)*newInfoDeriv->allUsed2DParmList->numParm)))==0)
	{
		perror("malloc");
		exit(-1);
	}

    /* release temporary parameter lists */
    destroyMadparmList(foundOutputList);
    destroyMadparmList(filtParmsNotRequestedList);

    return newInfoDeriv;
}


/***********************************************************************
*
* destroyInfoDerived - frees all memory for given InfoDerived struct
*
*   arguments:
*      InfoDerived * info - pointer to struct to free
*
*   returns - void
*/
void destroyInfoDerived(InfoDerived * info)
{
    int i = 0;

    if (info == NULL)
        return;

    if (info->numDervMeth != 0)
    {
        for(i=0; i< info->numDervMeth; i++)
            destroyInfoMethod(info->infoMethodArr[i]);
        free(info->infoMethodArr);
    }

    if (info->numMultiRowMeth != 0)
    {
        for(i=0; i< info->numMultiRowMeth; i++)
            destroyInfoMultiRowMethod(info->infoMultiRowMethArr[i]);
        free(info->infoMultiRowMethArr);
    }

    if (info->meas1DParmList != NULL)
        destroyMadparmList(info->meas1DParmList);

    if (info->meas1DCodeList != NULL)
        free(info->meas1DCodeList);

    if (info->meas2DParmList != NULL)
        destroyMadparmList(info->meas2DParmList);

    if (info->meas2DCodeList != NULL)
        free(info->meas2DCodeList);

    if (info->requestedParmList != NULL)
        destroyMadparmList(info->requestedParmList);

    if (info->req1DParmList != NULL)
        destroyMadparmList(info->req1DParmList);

    if (info->mapReq1DParmList != NULL)
        free(info->mapReq1DParmList);

    if (info->req2DParmList != NULL)
        destroyMadparmList(info->req2DParmList);

    if (info->mapReq2DParmList != NULL)
        free(info->mapReq2DParmList);

    if (info->unavailParmList != NULL)
        destroyMadparmList(info->unavailParmList);

    if (info->allUsed1DParmList != NULL)
        destroyMadparmList(info->allUsed1DParmList);

    if (info->allAvail1DParmList != NULL)
        destroyMadparmList(info->allAvail1DParmList);

    if (info->allUsed2DParmList != NULL)
        destroyMadparmList(info->allUsed2DParmList);

    if (info->allAvail2DParmList != NULL)
        destroyMadparmList(info->allAvail2DParmList);

    if (info->all1DParm != NULL)
        free(info->all1DParm);

    if (info->all2DParm != NULL)
        free(info->all2DParm);

    if (info->tmpInputParm != NULL)
        free(info->tmpInputParm);

    if (info->tmpOutputParm != NULL)
        free(info->tmpOutputParm);

    if (info->filt1DList != NULL)
        destroyMadfilterList(info->filt1DList);

    if (info->onlyMeas1DList != NULL)
        free(info->onlyMeas1DList);

    if (info->mapFilt1DParm != NULL)
        free(info->mapFilt1DParm);

    if (info->filt2DList != NULL)
        destroyMadfilterList(info->filt2DList);

    if (info->onlyMeas2DList != NULL)
        free(info->onlyMeas2DList);

    if (info->mapFilt2DParm != NULL)
        free(info->mapFilt2DParm);

    free(info);
}

/***********************************************************************
*
* dispatchMethod - calls the derived method set by methIndex
*
*   arguments:
*      InfoDerived * infoDeriv - pointer to struct to update by
*                                calling method
*      int methIndex - index of method being run
*      FILE * errFile - error file for methods to write to
*
*   writes error message to errFile if error occurs
*
*   returns - 0 if no error thrown by underlying method
*/
int dispatchMethod(InfoDerived * infoDeriv, int methIndex, FILE * errFile)
{
    int i=0;
    int result = 0;
    double tmpInput = 0.0;
    int tmpIndex = 0;
    int inputMissing = 0;  /* checks if any inputs missing */

    /* copy all inputs into infoDeriv->tmpInputParm */
    for (i=0; i<gCompExtList[methIndex].inputCount; i++)
    {
        /* check if its a 1D input */
        if (infoDeriv->infoMethodArr[methIndex]->inputMap[2*i] == 1)
        {
            tmpInput = infoDeriv->all1DParm[infoDeriv->infoMethodArr[methIndex]->inputMap[2*i + 1]];
            /* check if its missing */
            if (isnan(tmpInput))
            {
                inputMissing = 1;
                break;
            }
            infoDeriv->tmpInputParm[i] = tmpInput;
        }
        else  /* its 2D input */
        {
            tmpInput = infoDeriv->all2DParm[infoDeriv->infoMethodArr[methIndex]->inputMap[2*i + 1]];
            /* check if its missing */
            if (isnan(tmpInput))
            {
                inputMissing = 1;
                break;
            }
            infoDeriv->tmpInputParm[i] = tmpInput;
        }
    } /* next input parameter */

    /* if all inputs exist, call method */
    if (!inputMissing)
    {

        /* This next line is the heart of madDerivedParm - this line    */
        /* uses a function pointer to call every derived method.        */
        /* gCompExtList is a list of all methods that derive parameters */

        result= (*(gCompExtList[methIndex].compExt)) (gCompExtList[methIndex].inputCount,
                                                      infoDeriv->tmpInputParm,
                                                      gCompExtList[methIndex].outputCount,
                                                      infoDeriv->tmpOutputParm,
                                                      errFile);
    }
    else /* input missing, set all outputs to missing */
    {
        result = 0;
        for (i=0; i<gCompExtList[methIndex].outputCount; i++)
            infoDeriv->tmpOutputParm[i] = missing;
    }

    /* finally copy data from infoDeriv->tmpOutputParm to infoDeriv->all1DParm (or all1DParm) */
    /* check if its a 1D method */
    if (infoDeriv->infoMethodArr[methIndex]->all1D)
    {
        for (i=0; i<gCompExtList[methIndex].outputCount; i++)
        {
            tmpIndex = infoDeriv->infoMethodArr[methIndex]->outputMap[i];
            /* ignore outputs with index == -1 */
            if (tmpIndex < 0)
                continue;
            infoDeriv->all1DParm[tmpIndex] = infoDeriv->tmpOutputParm[i];
        }
    }
    else /* its 2D output */
    {
        for (i=0; i<gCompExtList[methIndex].outputCount; i++)
        {
            tmpIndex = infoDeriv->infoMethodArr[methIndex]->outputMap[i];
            /* ignore outputs with index == -1 */
            if (tmpIndex < 0)
                continue;
            infoDeriv->all2DParm[tmpIndex] = infoDeriv->tmpOutputParm[i];
        }
    }

    return (result);
}


/***********************************************************************
*
* dispatchMultiRowMethod - calls the derived multi-row method set by methIndex
*
*   arguments:
*      InfoDerived * infoDeriv - pointer to struct to update by
*                                calling method
*      int methIndex - index of method being run
*      FILE * errFile - error file for methods to write to
*
*   writes error message to errFile if error occurs
*
*   returns - 0 if no error thrown by underlying method
*/
int dispatchMultiRowMethod(InfoDerived * infoDeriv,
                           int methIndex,
                           int numRows,
                           FILE * errFile)
{
    int i=0;
    int j=0;
    int result = 0;
    int inputMissing = 0;  /* checks if any 1D inputs missing */
    InfoMultiRowMethod * infoMultiRowMeth = NULL;

    /* shorten code with a pointer to needed InfoMultiRowMethod */
    infoMultiRowMeth = infoDeriv->infoMultiRowMethArr[methIndex];

    /* check that no 1D input is missing */
    for (i=0; i<gCompExtMultiRowList[methIndex].inputCount; i++)
    {
        /* check if its a 1D input */
        if (gCompExtMultiRowList[methIndex].inputMnemType[i] == 1)
        {
            if (isnan(infoMultiRowMeth->inputArr[i][0]))
                inputMissing = 1;
        }

    } /* next input parameter */

    /* if all inputs exist, call method */
    if (!inputMissing)
    {

        /* This next line uses a function pointer to call the derived multi-row method.   */
        /* gCompExtMultiRowList is a list of all multi-row methods that derive parameters */

        result= (*(gCompExtMultiRowList[methIndex].compExt)) (numRows,
                                                              gCompExtMultiRowList[methIndex].inputCount,
                                                              infoMultiRowMeth->inputArr,
                                                              gCompExtMultiRowList[methIndex].outputCount,
                                                              infoMultiRowMeth->outputArr,
                                                              errFile);
    }
    else /* input missing, set all outputs to missing */
    {
        result = 0;
        for (i=0; i<gCompExtList[methIndex].outputCount; i++)
        {
            /* check if its a 1D output */
            if (gCompExtMultiRowList[methIndex].outputMnemType[i] == 1)
                infoMultiRowMeth->outputArr[i][0] = missing;
            else /* its 2D */
            {
                /* loop through each row, and set to missing */
                for (j=0; j<gCompExtMultiRowList[methIndex].outputCount; j++)
                    infoMultiRowMeth->outputArr[i][j] = missing;
            }
        }
    }

    return (result);
}


/***********************************************************************
*
* checkIf1DMethodNeeded - if 1D method is needed, calls make1DMethodNeeded
*
*   arguments:
*      InfoDerived * infoDeriv - pointer to struct to update if
*                                method is needed
*      int methIndex - index of method being checked
*      MadparmList filtParmsNotRequestedList - additional parameters needed
*
*     Method being checked has already been found to be one
*     that can be used successfully given measured 1D parameter
*     and outputs of earlier derived methods.
*
*   returns - void
*/
void checkIf1DMethodNeeded(InfoDerived * infoDeriv,
                           int methIndex,
                           MadparmList * filtParmsNotRequestedList)
{
    int i=0;

    const char * thisMnem = NULL;

    /* loop through all output parameters */
    for (i=0; i<gCompExtList[methIndex].outputCount; i++)
    {
        thisMnem = gCompExtList[methIndex].outputMnemList[i];

        /* check if in requestedParmList or filtParmsNotRequestedList */
        if (hasParm(infoDeriv->requestedParmList, thisMnem) ||
            hasParm(filtParmsNotRequestedList, thisMnem))
        {
            /* check if not yet in allUsed1DParmList or allUsed2DParmList */
            if (!hasParm(infoDeriv->allUsed1DParmList, thisMnem) &&
                !hasParm(infoDeriv->allUsed2DParmList, thisMnem))
            {
                /* this method is needed */
                make1DMethodNeeded(infoDeriv, methIndex);
                return;
            }
        }
    } /* check next output parameter */
}


/***********************************************************************
*
* checkIf2DMethodNeeded - if 2D method is needed, calls make2DMethodNeeded
*
*   arguments:
*      InfoDerived * infoDeriv - pointer to struct to update if
*                                method is needed
*      int methIndex - index of method being checked
*      MadparmList filtParmsNotRequestedList - additional parameters needed
*
*     Method being checked has already been found to be one
*     that can be used successfully given measured 1 and 2D parameters
*     and outputs of earlier derived methods.
*
*   returns - void
*/
void checkIf2DMethodNeeded(InfoDerived * infoDeriv,
                           int methIndex,
                           MadparmList * filtParmsNotRequestedList)
{
    int i=0;

    const char * thisMnem = NULL;

    /* loop through all output parameters */
    for (i=0; i<gCompExtList[methIndex].outputCount; i++)
    {
        thisMnem = gCompExtList[methIndex].outputMnemList[i];

        /* check if in requestedParmList or filtParmsNotRequestedList */
        if (hasParm(infoDeriv->requestedParmList, thisMnem) ||
            hasParm(filtParmsNotRequestedList, thisMnem))
        {
            /* check if not in allUsed1DParmList */
            if (hasParm(infoDeriv->allUsed1DParmList, thisMnem))
                continue;

            /* check if not yet in allUsed2DParmList */
            if (!hasParm(infoDeriv->allUsed2DParmList, thisMnem))
            {
                /* this method is needed */
                make2DMethodNeeded(infoDeriv, methIndex);
                return;
            }
        }
    } /* check next output parameter */
}



/***********************************************************************
*
* make1DMethodNeeded - sets this method and all it depends on as needed
*
*   arguments:
*      InfoDerived * infoDeriv - pointer to struct to update
*      int methIndex - index of method need
*
*     This is a recursive method that returns only after all dependent
*     methods have been set as needed.  It adds all input and output
*     parameters to allUsed1DParmList if not there already.
*
*   returns - void
*/
void make1DMethodNeeded(InfoDerived * infoDeriv, int methIndex)
{
    int i = 0;
    const char * thisMnem;

    /* if method is already marked as needed, return immediately */
    if (infoDeriv->infoMethodArr[methIndex]->isNeeded == 1)
        return;

    /* otherwise, mark it as needed, add all input and output  */
    /* parameters to allUsed1DParmList if not there already,   */
    /* and then call make1DMethodNeeded for all methods in     */
    /* neededMethods                                           */

    infoDeriv->infoMethodArr[methIndex]->isNeeded = 1;

    for (i=0; i<gCompExtList[methIndex].inputCount; i++)
    {
        thisMnem = gCompExtList[methIndex].inputMnemList[i];
        if (!hasParm(infoDeriv->allUsed1DParmList, thisMnem) &&
            !hasParm(infoDeriv->allUsed2DParmList, thisMnem))
        {
            appendMadparm(infoDeriv->allUsed1DParmList, thisMnem);
        }
    }

    for (i=0; i<gCompExtList[methIndex].outputCount; i++)
    {
        thisMnem = gCompExtList[methIndex].outputMnemList[i];
        if (!hasParm(infoDeriv->allUsed1DParmList, thisMnem) &&
            !hasParm(infoDeriv->allUsed2DParmList, thisMnem))
        {
            appendMadparm(infoDeriv->allUsed1DParmList, thisMnem);
        }
    }

    for (i=0; i<infoDeriv->infoMethodArr[methIndex]->numInputMethods; i++)
        make1DMethodNeeded(infoDeriv, infoDeriv->infoMethodArr[methIndex]->neededMethods[i]);
}


/***********************************************************************
*
* make2DMethodNeeded - sets this method and all it depends on as needed
*
*   arguments:
*      InfoDerived * infoDeriv - pointer to struct to update
*      int methIndex - index of method need
*
*     This is a recursive method that returns only after all dependent
*     methods have been set as needed.  It adds all input and output
*     parameters to allUsed2DParmList or allUsed2DParmList if not there already.
*
*   returns - void
*/
void make2DMethodNeeded(InfoDerived * infoDeriv, int methIndex)
{
    int i = 0;
    const char * thisMnem;

    /* if method is already marked as needed, return immediately */
    if (infoDeriv->infoMethodArr[methIndex]->isNeeded == 1)
        return;

    /* otherwise, mark it as needed, add all input and output  */
    /* parameters to allUsed2DParmList if not there already,   */
    /* (or not in allUsed1DParmList),  and then recursively    */
    /* call make2DMethodNeeded for all methods in              */
    /* neededMethods                                           */

    infoDeriv->infoMethodArr[methIndex]->isNeeded = 1;

    for (i=0; i<gCompExtList[methIndex].inputCount; i++)
    {
        thisMnem = gCompExtList[methIndex].inputMnemList[i];
        if (hasParm(infoDeriv->allUsed1DParmList, thisMnem))
            continue;
        if (!hasParm(infoDeriv->allUsed2DParmList, thisMnem))
        {
            appendMadparm(infoDeriv->allUsed2DParmList, thisMnem);
        }
    }

    for (i=0; i<gCompExtList[methIndex].outputCount; i++)
    {
        thisMnem = gCompExtList[methIndex].outputMnemList[i];
        if (hasParm(infoDeriv->allUsed1DParmList, thisMnem))
            continue;
        if (!hasParm(infoDeriv->allUsed2DParmList, thisMnem))
        {
            appendMadparm(infoDeriv->allUsed2DParmList, thisMnem);
        }
    }

    for (i=0; i<infoDeriv->infoMethodArr[methIndex]->numInputMethods; i++)
    {
        if (infoDeriv->infoMethodArr[methIndex]->all1D)
            make1DMethodNeeded(infoDeriv, infoDeriv->infoMethodArr[methIndex]->neededMethods[i]);
        else
            make2DMethodNeeded(infoDeriv, infoDeriv->infoMethodArr[methIndex]->neededMethods[i]);
    }
}


/***********************************************************************
*
* checkIfMultiRowMethodNeeded - makes multi-row method needed if required
*
*   arguments:
*      InfoDerived * infoDeriv - pointer to struct to update if
*                                multi-row method is needed
*      int methIndex - index of multi-row method being checked
*
*     Multi-row method being checked has already been found to be one
*     that can be used successfully given measured 1 and 2D parameters
*     and outputs of earlier derived methods. Reallocates InfoMultiRowMethod->
*     inputArr and outputArr if needed, and sets up inputMap.
*
*   returns - void
*/
void checkIfMultiRowMethodNeeded(InfoDerived * infoDeriv,
                                 int methIndex)
{
    int i=0;
    int j=0;

    const char * thisMnem = NULL;

    /* set the method by default to not needed */
    infoDeriv->infoMultiRowMethArr[methIndex]->isNeeded = 0;

    /* loop through all output parameters */
    for (i=0; i<gCompExtMultiRowList[methIndex].outputCount; i++)
    {
        thisMnem = gCompExtMultiRowList[methIndex].outputMnemList[i];

        /* check if in requestedParmList */
        if (hasParm(infoDeriv->requestedParmList, thisMnem))
        {
            /* check if not in allUsed1DParmList */
            if (hasParm(infoDeriv->allUsed1DParmList, thisMnem))
                continue;

            /* check if not yet in allUsed2DParmList */
            if (!hasParm(infoDeriv->allUsed2DParmList, thisMnem))
            {
                /* this output parameter is needed */

                infoDeriv->anyMultRowNeeded = 1;

                /* check if its 1D or 2D */
                if (gCompExtMultiRowList[methIndex].outputMnemType[i] == 1)
                {
                    appendMadparm(infoDeriv->allUsed1DParmList, thisMnem);
                    appendMadparm(infoDeriv->allAvail1DParmList, thisMnem);
                }
                else /* its a 2D output */
                {
                    appendMadparm(infoDeriv->allUsed2DParmList, thisMnem);
                    appendMadparm(infoDeriv->allAvail2DParmList, thisMnem);
                }

                /* mark it as needed if not already set */
                if (infoDeriv->infoMultiRowMethArr[methIndex]->isNeeded == 1) continue;

                infoDeriv->infoMultiRowMethArr[methIndex]->isNeeded = 1;

                /* loop through its inputs to set up inputMap and reallocate inputArr */
                for (j=0; j<infoDeriv->infoMultiRowMethArr[methIndex]->numInputs; j++)
                {
                    /* is it 1D? */
                    if (gCompExtMultiRowList[methIndex].inputMnemType[j] == 1)
                    {
                        infoDeriv->infoMultiRowMethArr[methIndex]->inputMap[j] = getIndex(infoDeriv->allUsed1DParmList,
                                                   gCompExtMultiRowList[methIndex].inputMnemList[j]);
                        assert(infoDeriv->infoMultiRowMethArr[methIndex]->inputMap[j] != -1);
                    }
                    else /* its a 2D input */
                    {
                        infoDeriv->infoMultiRowMethArr[methIndex]->inputMap[j] = getIndex(infoDeriv->allUsed2DParmList,
                                                   gCompExtMultiRowList[methIndex].inputMnemList[j]);
                        assert(infoDeriv->infoMultiRowMethArr[methIndex]->inputMap[j] != -1);

                        /* reallocate inputArr to handle 2D data */
                        free(infoDeriv->infoMultiRowMethArr[methIndex]->inputArr[j]);
                        infoDeriv->infoMultiRowMethArr[methIndex]->inputArr[j] = (double *)malloc(sizeof(double)*MAX_2D_ROWS);
                        if (infoDeriv->infoMultiRowMethArr[methIndex]->inputArr[j] == 0)
                        {
                            perror("malloc");
                            exit(-1);
                        }
                    }
                } /* next input */
            }
        }
    } /* check next output parameter */

    /* if this method is needed, reallocate outputArr if 2D and add outputs to used and avail lists */
    if (infoDeriv->infoMultiRowMethArr[methIndex]->isNeeded)
    {
        /* loop through all output parameters */
        for (i=0; i<gCompExtMultiRowList[methIndex].outputCount; i++)
        {
            if (gCompExtMultiRowList[methIndex].outputMnemType[i] == 2)
            {

                /* reallocate inputArr to handle 2D data */
                free(infoDeriv->infoMultiRowMethArr[methIndex]->outputArr[i]);
                infoDeriv->infoMultiRowMethArr[methIndex]->outputArr[i] = (double *)malloc(sizeof(double)*MAX_2D_ROWS);
                if (infoDeriv->infoMultiRowMethArr[methIndex]->outputArr[i] == 0)
                {
                    perror("malloc");
                    exit(-1);
                }
            }
        }

    }
}


/***********************************************************************
*
* hasOutput - returns 1 if CompiledExt outputs given mnem, 0 otherwise
*
*   arguments:
*      const CompiledExt * ext - pointer to compiled extension being analyzed
*      const char *  mnem - pointer to mnemonic
*
*   returns  1 if CompiledExt outputs given mnem, 0 otherwise
*/
int hasOutput(const CompiledExt * exten, const char * mnem)
{
    int i = 0;

    for (i=0; i<exten->outputCount; i++)
    {
        if (strcmp(exten->outputMnemList[i], mnem) == 0)
            return 1;
    }
    return 0;
}

