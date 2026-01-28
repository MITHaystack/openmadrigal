"""The derivation module creates new cedar objects with possibly derived parameters

The fundamental inputs are a list of desired parameters, and an existing cedar.MadrigalCedarFile object.

Its fundamental output is a new cedar.MadrigalCedarFile object with the requested parameters

The derivation was built to be both flexible and fast. It tries to minimize the number of calls to 
derive parameters by testing filters as soon as possible in order to drop records or 2D rows as soon as 
possible.  This basic algorithm is as follows:

for each MadrigalDataRecord:
  - if the analysis says a filter depends on an underivable 
    parameter, the record is rejected immediately.
  - Any filter that depends on only 1D measured data is applied
  - all 1D data is derived.  But any filter that depends only on derived 1D data
      is called as soon as all its inputs are derived.
  - for each 2D row:
      - Any filter that depends on only 2D measured data is applied
      - all 2D data is derived.  But any filter that depends only on derived 2D data
      is called as soon as all its inputs are derived.
      

$Id: derivation.py 7655 2024-06-27 20:20:49Z kcariglia $
"""

# standard python imports
import collections
import math
import copy
import os
import datetime, calendar
import random
import tempfile
import types

# third party imports
import numpy
import h5py
import aacgmv2
import pymap3d

# Madrigal imports
import madrigal.cedar
import madrigal.data
import madrigal.metadata
import madrigal._derive


"""Edit the following OrderedDict to modify the list of MadrigalDerivedMethods.

The name of the method is the key.  The value is a list with between two and four items.
    The first item is the input mnemonic(s).
    The second item is the output mnemonic(s).
    The optional third parameter is either 'python' or 'C'.  If only two parameters, 'C' is assumed.
        This determines whether the method is implementated on C (or Fortran wrapped in C), or python.
    The optional fourth parameter is a list of kinst values for which the derivation is valid (used in
        statistical models, etc).  This feature requires 'python' to be the implementation method.
    
The order of these derivation methods matter - they will be called in a single pass from first to last.  The MadrigalDerivationPlan
determines which need to be called, and what parameters are derivable given the initial measured parameters.
Any parameter will be derived by the first available method that has that parameter as an output and
for which all input parameters are measured or themselves derivable.

For the C derivation methods, the methods are implemented in source/madc/madrec/madDeriveMethods.c.  All
methods must have a signature of the form:

int methodName(int inCount,
              double * inputArr,
              int outCount,
              double * outputArr,
              FILE * errFile)
              
where inCount is the number of input arguments, and inputArr is a double array of length inCount, with
values for each input variable.  Likewise, outCount is the number of output arguments, and outputArr 
is already allocated double array of length outCount, where the method sets the values for each 
output variable when it returns.  If values cannot be calulated, that output value is set to nan.

For the python derivation methods, all methods are defined in madrigal.derivation.MadrigalDerivationMethods
in this module.  Each method has two arguments - a double array of input values of length the number of input
variables, and the output array the length of the number of output variable.  As in the C, the output
array is passed in to the derivation method preallocated.
"""
MadrigalDerivedMethods = collections.OrderedDict()

#  Pure time 
MadrigalDerivedMethods["getFirstTime"] = [("UT1_UNIX", "UT2_UNIX",),
                                       ("FIRST_IBYR", "FIRST_IBDT", "FIRST_IBHM", "FIRST_IBCS",), 'python']
MadrigalDerivedMethods["getPrologTime"] = [("UT1_UNIX", "UT2_UNIX",),
                                           ("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",)]
MadrigalDerivedMethods["getByear"] = [("IBYR",), 
                                      ("BYEAR",)]
MadrigalDerivedMethods["getTime"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                     ("YEAR", "MONTH", "DAY", "HOUR", "MIN", "SEC", "CSEC",)]
MadrigalDerivedMethods["getBmd"] = [("IBDT",),
                                    ("BMD",)]
MadrigalDerivedMethods["getBMonthDay"] = [("IBDT",),
                                          ("BMONTH","BDAY",)]
MadrigalDerivedMethods["getMd"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                   ("MD",)]
MadrigalDerivedMethods["getUtUnix"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                       ("UT1_UNIX", "UT2_UNIX",)]
MadrigalDerivedMethods["getDayno"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                      ("DAYNO",)]
MadrigalDerivedMethods["getBhm"] = [("IBHM",),
                                    ("BHM",)]
MadrigalDerivedMethods["getBhhmmss"] = [("IBHM", "IBCS",),
                                        ("BHHMMSS",)]
MadrigalDerivedMethods["getEhhmmss"] = [("IEHM", "IECS",),
                                        ("EHHMMSS",)]
MadrigalDerivedMethods["getHm"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                   ("HM",)]
MadrigalDerivedMethods["getUth"] = [("FIRST_IBYR", "FIRST_IBDT", "FIRST_IBHM", "FIRST_IBCS",
                                             "IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                    ("UTH",)]
MadrigalDerivedMethods["getUts"] = [("FIRST_IBYR", "FIRST_IBDT", "FIRST_IBHM", "FIRST_IBCS",
                                             "IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                    ("UTS",)]
MadrigalDerivedMethods["getBUth"] = [("FIRST_IBYR", "FIRST_IBDT", "FIRST_IBHM", "FIRST_IBCS",
                                             "IBYR", "IBDT", "IBHM", "IBCS",),
                                     ("B_UTH",)]
MadrigalDerivedMethods["getInttms"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                       ("INTTMS",)]
MadrigalDerivedMethods["getInttmm"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                       ("INTTMM",)]
MadrigalDerivedMethods["getDatntd"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                       ("DATNTD",)]
MadrigalDerivedMethods["getUt"] = [("UTH",),
                                   ("UT",)]
MadrigalDerivedMethods["getBegUt"] = [("B_UTH",),
                                      ("BEG_UT",)]
MadrigalDerivedMethods["getJdayno"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                       ("JDAYNO",)]
MadrigalDerivedMethods["getJulian_date"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS", "JDAYNO",),
                                            ("JULIAN_DATE",)]
MadrigalDerivedMethods["getJulian_day"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                           ("JULIAN_DAY",)]
MadrigalDerivedMethods["getUt1"] = [("IBYR", "IBDT", "IBHM", "IBCS",),
                                    ("UT1",)]
MadrigalDerivedMethods["getUt2"] = [("IEYR", "IEDT", "IEHM", "IECS",),
                                    ("UT2",)]
MadrigalDerivedMethods["getDut21"] = [("UT1", "UT2",),
                                      ("DUT21",)]
MadrigalDerivedMethods["getFyear"] = [("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS",),
                                      ("FYEAR",)]

# time and space 

MadrigalDerivedMethods["getStation"] = [("KINST",),
                                        ("GDLATR", "GDLONR", "GALTR",), 'python']
MadrigalDerivedMethods["getAltInc"] = [("ROW", "ALTB", "ALTAV",),
                                       ("GDALT",)]
MadrigalDerivedMethods["getAveAlt"] = [("ALTB", "ALTE",),
                                       ("GDALT",)]
MadrigalDerivedMethods["getAveDAlt"] = [("DALTB", "DALTE",),
                                        ("DGDALT",)]
MadrigalDerivedMethods["getResl"] = [("MRESL",),
                                     ("RESL",)]
MadrigalDerivedMethods["getAzmDaz"] = [("AZ1", "AZ2",),
                                       ("AZM", "DAZ",)]
MadrigalDerivedMethods["getDAzmDDaz"] = [("DAZ1", "DAZ2",),
                                         ("DAZM", "DDAZ",)]
MadrigalDerivedMethods["getElmDel"] = [("EL1", "EL2",),
                                       ("ELM", "DEL",)]
MadrigalDerivedMethods["getDElmDDel"] = [("DEL1", "DEL2",),
                                         ("DELM", "DDEL",)]
MadrigalDerivedMethods["getGeod"] = [("KINST", "AZM", "ELM", "RANGE",),
                                     ("GDLAT", "GLON", "GDALT",), 'python']
MadrigalDerivedMethods["getDGeod"] = [("KINST", "AZM", "DAZM", "ELM", "DELM", "RANGE", "DRANGE",),
                                      ("DGDLAT", "DGLON", "DGDALT",), 'python']
MadrigalDerivedMethods["getGeodGdalt"] = [("KINST", "AZM", "ELM", "GDALT",),
                                          ("GDLAT", "GLON",), 'python']
MadrigalDerivedMethods["getGeodAlt"] = [("GDLATR", "GDLONR",),
                                        ("GDLAT", "GLON",), 'python']
MadrigalDerivedMethods["getAzElRange"] = [("GDLAT", "GLON", "GDALT", "GDLATR", "GDLONR", "GALTR",),
                                          ("AZM","ELM", "RANGE",), 'python']
MadrigalDerivedMethods["getSZen"] = [("UT1", "UT2", "GDLAT", "GLON",),
                                     ("SZEN",)]
MadrigalDerivedMethods["getSltmut"] = [("UT1", "UT2", "GLON",),
                                       ("SLTMUT",)]
MadrigalDerivedMethods["getSlt"] = [("UT1", "UT2", "GLON",),
                                    ("SLT",)]
MadrigalDerivedMethods["getSdwHt"] = [("UT1", "UT2", "GDLAT", "GLON",),
                                      ("SDWHT",)]
MadrigalDerivedMethods["getSuntime"] = [("UT1", "UT2", "GDLAT", "GLON", "GDALT",),
                                        ("SUNRISE", "SUNSET", "SUNRISE_HOUR", "SUNSET_HOUR",)]
MadrigalDerivedMethods["getTecGdalt"] = [("TEC", "GDLAT", "GLON",),
                                         ("GDALT",)]
MadrigalDerivedMethods["getGcdist"] = [("GDLATR", "GDLONR", "GDLAT", "GLON",),
                                       ("GCDIST",)]

# magnetic parameters 
MadrigalDerivedMethods["getB_up"] = [("BD",),
                                    ("B_UP",), 'python']
MadrigalDerivedMethods["getBd"] = [("B_UP",),
                                    ("BD",), 'python']
MadrigalDerivedMethods["getMag"] = [("UT1", "UT2", "GDLAT", "GLON", "GDALT",),
                                    ("BN","BE","BD","BMAG",)]
MadrigalDerivedMethods["getMag2"] = [("UT1", "UT2", "GDLAT", "GLON", "GDALT",),
                                    ("BDEC","BINC","LSHELL","DIPLAT","INVLAT",
                                     "APLAT","APLON","MAGCONJLAT","MAGCONJLON",)]
MadrigalDerivedMethods["getDiff_B_up"] = [("DIFF_BD",),
                                    ("DIFF_B_UP",), 'python']
MadrigalDerivedMethods["getDiff_Bd"] = [("DIFF_B_UP",),
                                    ("DIFF_BD",), 'python']
MadrigalDerivedMethods["getMagStat"] = [("UT1", "UT2", "GDLAT", "GLON", "GDALT","GDLATR", "GDLONR", "GALTR",),
                                        ("CXR","CYR","CZR",)]
MadrigalDerivedMethods["getSltc"] = [("UT1", "UT2", "MAGCONJLON",),
                                     ("SLTC",)]
MadrigalDerivedMethods["getAplt"] = [("UT1", "UT2", "APLON",),
                                     ("APLT",)]
MadrigalDerivedMethods["getSZenc"] = [("UT1", "UT2", "MAGCONJLAT","MAGCONJLON",),
                                      ("SZENC",)]
MadrigalDerivedMethods["getConjSun"] = [("UT1", "UT2", "MAGCONJLAT", "MAGCONJLON", "GDALT",),
                                        ("CONJ_SUNRISE", "CONJ_SUNSET", "CONJ_SUNRISE_H", "CONJ_SUNSET_H", "MAGCONJSDWHT",)]
MadrigalDerivedMethods["getTsygan"] = [("UT1_UNIX", "UT2_UNIX", "UT1", "UT2", "GDLAT", "GLON", "GDALT",),
                                       ("TSYG_EQ_XGSM","TSYG_EQ_YGSM","TSYG_EQ_XGSE","TSYG_EQ_YGSE",), 'python']
MadrigalDerivedMethods["getAacgm"] = [("UT1_UNIX", "UT2_UNIX", "GDLAT", "GLON", "GDALT",),
                                      ("AACGM_LAT","AACGM_LONG", "MLT"), 'python']
MadrigalDerivedMethods["fromAacgm"] = [("UT1_UNIX", "UT2_UNIX", "AACGM_LAT","AACGM_LONG","GDALT",),
                                       ("GDLAT", "GLON",), 'python']
MadrigalDerivedMethods["getEregion"] = [("UT1", "UT2", "GDLAT", "GLON", "GDALT",),
                                        ("E_REG_S_LAT", "E_REG_S_LON", "E_REG_S_SDWHT",
                                         "E_REG_N_LAT", "E_REG_N_LON", "E_REG_N_SDWHT",)]
MadrigalDerivedMethods["getAspect"] = [("UT1", "UT2", "GDLATR", "GDLONR", "GALTR","AZM", "ELM", "RANGE",),
                                       ("ASPECT",)]

# geophysical parameters 

MadrigalDerivedMethods["getGeo"] = [("UT1_UNIX", "UT2_UNIX",),
                                    ("KP", "AP3", "AP", "F10.7", "FBAR",), 'python']
MadrigalDerivedMethods["getDst"] = [("UT1_UNIX", "UT2_UNIX",),
                                    ("DST",), 'python']
MadrigalDerivedMethods["getFof2Mlh"] = [("UT1_UNIX", "UT2_UNIX", "KINST",),
                                        ("FOF2_MLH",), 'python', [30,31,32,5340,5360]]

# isr parameters 
MadrigalDerivedMethods["getPopl"] = [("POP",),
                                     ("POPL",)]
MadrigalDerivedMethods["getPop"] = [("POPL",),
                                    ("POP",)]
MadrigalDerivedMethods["getNeNe8"] = [("NE8",),
                                    ("NE",), 'python']
MadrigalDerivedMethods["getDNeDNe8"] = [("DNE8",),
                                    ("DNE",), 'python']
MadrigalDerivedMethods["getNel"] = [("NE",),
                                    ("NEL",)]
MadrigalDerivedMethods["getNe"] = [("NEL",),
                                   ("NE",)]
MadrigalDerivedMethods["getDNel"] = [("DNE",),
                                     ("DNEL",)]
MadrigalDerivedMethods["getDNe"] = [("DNEL",),
                                    ("DNE",)]
MadrigalDerivedMethods["getNemaxl"] = [("NEMAX",),
                                       ("NEMAXL",)]
MadrigalDerivedMethods["getNemax"] = [("NEMAXL",),
                                      ("NEMAX",)]
MadrigalDerivedMethods["getTr"] = [("TE","TI",),
                                   ("TR",)]
MadrigalDerivedMethods["getTe"] = [("TR","TI",),
                                   ("TE",)]
MadrigalDerivedMethods["getTi"] = [("TE","TR",),
                                   ("TI",)]
MadrigalDerivedMethods["getDteCctitr"] = [("CCTITR","TI", "TR", "DTI", "DTR",),
                                          ("DTE",)]
MadrigalDerivedMethods["getDte"] = [("TE","TI", "TR", "DTI", "DTR",),
                                    ("DTE",)]
MadrigalDerivedMethods["getCol"] = [("CO",),
                                    ("COL",)]
MadrigalDerivedMethods["getCo"] = [("COL",),
                                   ("CO",)]
MadrigalDerivedMethods["getNeNel"] = [("TI","TR", "POPL", "ASPECT",),
                                      ("NE", "NEL",)]
MadrigalDerivedMethods["getDNeDNel"] = [("TI","TR", "POPL", "ASPECT", "DTI","DTR", "DPOPL",),
                                        ("DNE", "DNEL",)]
MadrigalDerivedMethods["getVisrNe"] = [("UT1_UNIX", "UT1", "KINST", "SLT", "GDALT", "GDLAT", "ELM",),
                                       ("NE_MODEL", "NEL_MODEL",), 'python', 
                                       [20,25,30,31,32,40,72,80,5340,5360]]
MadrigalDerivedMethods["getVisrTe"] = [("UT1_UNIX", "UT1", "KINST", "SLT", "GDALT", "GDLAT", "ELM",),
                                       ("TE_MODEL",), 'python', 
                                       [20,25,30,31,32,40,72,80,95,5340,5360]]
MadrigalDerivedMethods["getVisrTi"] = [("UT1_UNIX", "UT1", "KINST", "SLT", "GDALT", "GDLAT", "ELM",),
                                       ("TI_MODEL",), 'python', 
                                       [20,25,30,31,32,40,72,80,95,5340,5360]]
MadrigalDerivedMethods["getVisrVo"] = [("UT1_UNIX", "UT1", "KINST", "SLT", "GDALT", "GDLAT", "ELM",),
                                       ("VO_MODEL",), 'python', 
                                       [20,30,32,80,95,5340,5360]]
MadrigalDerivedMethods["getVisrHNMax"] = [("UT1_UNIX", "UT1", "KINST", "SLT", "GDALT", "GDLAT", "ELM",),
                                          ("HMAX_MODEL", "NMAX_MODEL",), 'python', 
                                          [20,25,30,31,32,40,72,80,95,5340,5360]]
MadrigalDerivedMethods["getVisrNeDiff"] = [("NE", "NE_MODEL",),
                                           ("NE_MODELDIFF",)]
MadrigalDerivedMethods["getVisrNelDiff"] = [("NEL", "NEL_MODEL",),
                                            ("NEL_MODELDIFF",)]
MadrigalDerivedMethods["getVisrTeDiff"] = [("TE", "TE_MODEL",),
                                           ("TE_MODELDIFF",)]
MadrigalDerivedMethods["getVisrTiDiff"] = [("TI", "TI_MODEL",),
                                           ("TI_MODELDIFF",)]
MadrigalDerivedMethods["getVisrVoDiff"] = [("VO", "VO_MODEL",),
                                           ("VO_MODELDIFF",)]
MadrigalDerivedMethods["getSn"] = [("SNP3",),
                                   ("SN",)]
MadrigalDerivedMethods["getSnp3"] = [("SN",),
                                     ("SNP3",)]
MadrigalDerivedMethods["getChip31"] = [("CHISQ",),
                                       ("CHIP3",)]
MadrigalDerivedMethods["getWchsq1"] = [("CHIP3",),
                                       ("WCHSQ",)]
MadrigalDerivedMethods["getChisq1"] = [("WCHSQ",),
                                       ("CHISQ",)]
MadrigalDerivedMethods["getChip32"] = [("WCHSQ",),
                                       ("CHIP3",)]
MadrigalDerivedMethods["getWchsq2"] = [("CHISQ",),
                                       ("WCHSQ",)]
MadrigalDerivedMethods["getChisq2"] = [("CHIP3",),
                                       ("CHISQ",)]

# vector transformations 
# ion velocity 
MadrigalDerivedMethods["getVi1Vi1f"] = [("VI1F",),
                                        ("VI1",)]
MadrigalDerivedMethods["getVi2Vi2f"] = [("VI2F",),
                                        ("VI2",)]
MadrigalDerivedMethods["getVipeVipe1"] = [("VIPE1",),
                                          ("VIPE",)]
MadrigalDerivedMethods["getVipeVipe2"] = [("VIPE2",),
                                          ("VIPE",)]
MadrigalDerivedMethods["getVipnVipn1"] = [("VIPN1",),
                                          ("VIPN",)]
MadrigalDerivedMethods["getVipnVipn2"] = [("VIPN2",),
                                          ("VIPN",)]
MadrigalDerivedMethods["getVi6Vipu"] = [("VI6",),
                                        ("VIPU",)]
MadrigalDerivedMethods["getViGeom"] = [("VI1", "VI2", "VI3", "BN", "BE", "BD", "BMAG",),
                                       ("VIPE", "VIPN", "VIPU",)]
MadrigalDerivedMethods["getViGeod"] = [("VIPE", "VIPN", "VIPU", "BN", "BE", "BD", "BMAG",),
                                       ("VI1", "VI2", "VI3",)]
# neutral velocity 
MadrigalDerivedMethods["getVn1Vn1p2"] = [("VN1P2",),
                                         ("VN1",)]
MadrigalDerivedMethods["getVn2Vn2p2"] = [("VN2P2",),
                                         ("VN2",)]
MadrigalDerivedMethods["getVnGeom"] = [("VN1", "VN2", "VN3", "BN", "BE", "BD", "BMAG",),
                                       ("VN4", "VN5", "VN6",)]
MadrigalDerivedMethods["getVnGeod"] = [("VN4", "VN5", "VN6", "BN", "BE", "BD", "BMAG",),
                                       ("VN1", "VN2", "VN3",)]
# electric field 
MadrigalDerivedMethods["getEFGeom"] = [("EE", "EN", "EU", "BN", "BE", "BD", "BMAG",),
                                       ("EPE", "EPN", "EAP",)]
MadrigalDerivedMethods["getEFGeod"] = [("EPE", "EPN", "EAP", "BN", "BE", "BD", "BMAG",),
                                       ("EE", "EN", "EU",)]
# current density 
MadrigalDerivedMethods["getJGeom"] = [("J1", "J2", "J3", "BN", "BE", "BD", "BMAG",),
                                      ("J4", "J5", "J6",)]
MadrigalDerivedMethods["getJGeod"] = [("J4", "J5", "J6", "BN", "BE", "BD", "BMAG",),
                                      ("J1", "J2", "J3",)]

# neutral atmosphere 
MadrigalDerivedMethods["getNeut"] = [("UT1_UNIX", "UT2_UNIX", "YEAR", "MONTH", "DAY", 
                                     "HOUR", "MIN", "SEC", "GDLAT", "GLON", "GDALT",),
                                     ("TNM", "TINFM", "MOL", "NTOTL", "NN2L",
                                      "NO2L", "NOL", "NARL", "NHEL", "NHL",
                                      "NN4SL", "NPRESL", "PSH",
                                      "DTNM", "DTINFM", "DMOL", "DNTOTL", "DNN2L",
                                      "DNO2L", "DNOL", "DNARL", "DNHEL", "DNHL",
                                      "DNN4SL", "DNPRESL", "DPSH",), 'python']
MadrigalDerivedMethods["getTn"] = [("TI", "TE", "NE", "PH+", "NOL", "NHL",
                                             "NN4SL", "NO2L", "NHEL",),
                                   ("TN",)]
MadrigalDerivedMethods["getTnNoPhp"] = [("TI", "TE", "NE", "NOL", "NHL",
                                             "NN4SL", "NO2L", "NHEL",),
                                        ("TN",)]
MadrigalDerivedMethods["getDTn"] = [("TI", "TE", "NE", "NOL", "NHL",
                                             "NN4SL", "NO2L", "NHEL",
                                             "DTI", "DTE", "DNE", "DNOL", "DNHL",
                                             "DNN4SL", "DNO2L", "DNHEL",),
                                    ("DTN",)]

# IRI model 
MadrigalDerivedMethods["getIri"] = [("UT1_UNIX", "UT2_UNIX", "YEAR", "MONTH", "DAY", 
                                     "HOUR", "MIN", "SEC", "GDLAT", "GLON", "GDALT",),
                                    ("NE_IRI", "NEL_IRI", "TN_IRI", "TI_IRI", "TE_IRI",
                                     "PO+_IRI", "PNO+_IRI", "PO2+_IRI", "PHE+_IRI", "PH+_IRI", "PN+_IRI",),
                                    'python']

# conductivity 
MadrigalDerivedMethods["getCond"] = [("TI", "TE", "NE", "PH+_IRI", "PO+_IRI", "NOL", "NN2L",
                                             "NO2L", "TNM", "BMAG",),
                                     ("PDCON", "PDCONL", "HLCON", "HLCONL",)]
MadrigalDerivedMethods["getDCond"] = [("TI", "TE", "NE", "PH+_IRI", "PO+_IRI", "NOL", "NN2L",
                                             "NO2L", "TNM", "BMAG",
                                             "DTI", "DTE", "DNE", "DNOL", "DNN2L",
                                             "DNO2L",),
                                      ("DPDCON", "DPDCONL", "DHLCON", "DHLCONL",)]


# interplanetary mag field 
MadrigalDerivedMethods["getImf"] = [("UT1_UNIX", "UT2_UNIX",),
                                    ("BXGSM", "BYGSM", "BZGSM", "BIMF",
                                     "BXGSE", "BYGSE", "BZGSE",
                                     "SWDEN", "SWSPD", "SWQ",), 'python']


def getLowerCaseSet(l):
    """getLowerCaseSet returns a new set that is all lowercase given an input list
    that may have upper case strings
    """
    return(set([s.lower() for s in l]))


def getLowerCaseList(l):
    """getLowerCaseList returns a new list that is all lowercase given an input list
    that may have upper case strings
    """
    return([s.lower() for s in l])


def getDerivableParms(inputParmList=[], kinst=None):
    """getDerivableParms is a method to determine what parameters can be derived given the input parameters.
    Time/prolog parameters ("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS", "KINDAT", "KINST",
    "RECNO") are always assumed to be known, even if default empty list passed in.
    
    Meant mainly for UI interfaces, because it does not keep 1D and 2D parameters separate, so it not used
    for the main derivation engine.
    
    Inputs:
    
        inputParmList - list of input parameters in any form (integer or mnemonic)
        
        kinst - if not None, then kinst value may be passed in to for use in methods that are kinst specific.
            If None, then all kinst specific methods are unavailable
        
    Returns a list of all parameters that can be derived, including time/prolog parms and
        inputParmList.  Order is order would be derived using ordering in MadrigalDerivedMethods
    """
    madParmObj = madrigal.data.MadrigalParameters()
    
    timeParameters = ("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS", "UT1_UNIX", "UT2_UNIX", "KINDAT", "KINST", "RECNO")
    
    inputParmList = [madParmObj.getParmMnemonic(parm) for parm in inputParmList] # make sure all mnemonics
    inputParms = [madParmObj.getParmMnemonic(parm) for parm in inputParmList if parm.upper() not in timeParameters] # get all parms in std form
    availParmsSet = set(inputParms) # python set allows for rapidly determining if all inputs are available
    availParmsSet.update(timeParameters)
    
    retList = list(timeParameters) + inputParms
    for key in list(MadrigalDerivedMethods.keys()):
        inputSet = set(MadrigalDerivedMethods[key][0])
        if inputSet.issubset(availParmsSet):
            if len(MadrigalDerivedMethods[key]) >= 4:
                if kinst not in MadrigalDerivedMethods[key][3]:
                    continue # did not pass kinst requirement

            # this method can be derived because all inputs available
            outputParms = MadrigalDerivedMethods[key][1]
            newAvailParms = []
            for parm in outputParms:
                if parm not in retList:
                    retList.append(parm)
                    newAvailParms.append(parm)
            if len(newAvailParms) > 0:
                availParmsSet.update(newAvailParms)
                
    return(retList)



def get1D2DDerivableParms(input1DParmList=[], input2DParmList=[], kinst=None):
    """get1D2DDerivableParms is a method to determine what 1 and 2D parameters can be derived given the 1 and 2D input parameters.
    Time/prolog parameters ("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS", "KINDAT", "KINST",
    "RECNO") are always assumed to be known, even if default empty list passed in.
    
    
    Inputs:
    
        input1DParmList - list of 1D input parameters in any form (integer or mnemonic) - Default is Empty list
        
        input2DParmList - list of 2D input parameters in any form (integer or mnemonic) - Default is Empty list
        
        kinst - if not None, then kinst value may be passed in to for use in methods that are kinst specific.
            If None, then all kinst specific methods are unavailable
        
    Returns a tuple of two lists (1D and 2D) of all parameters that can be derived, including time/prolog parms and
        inputParmList.  Order is order would be derived using ordering in MadrigalDerivedMethods
    """
    madParmObj = madrigal.data.MadrigalParameters()
    
    timeParameters = ("IBYR", "IBDT", "IBHM", "IBCS", "IEYR", "IEDT", "IEHM", "IECS", "UT1_UNIX", "UT2_UNIX", "KINDAT", "KINST", "RECNO")
    
    input1DParmList = [madParmObj.getParmMnemonic(parm) for parm in input1DParmList] # make sure all mnemonics
    input1DParms = [madParmObj.getParmMnemonic(parm) for parm in input1DParmList if parm.upper() not in timeParameters] # get all parms in std form
    input2DParms = [madParmObj.getParmMnemonic(parm) for parm in input2DParmList] # make sure all mnemonics
    
    avail1DParmsSet = set(input1DParms) # python set allows for rapidly determining if all inputs are available
    avail1DParmsSet.update(timeParameters)
    availParmsSet = set(input1DParms + input2DParms + list(timeParameters)) # all parms
    
    ret1DList = list(timeParameters) + input1DParms 
    ret2DList = [p for p in input2DParms]
    for key in MadrigalDerivedMethods:
        inputSet = set(MadrigalDerivedMethods[key][0])
        if inputSet.issubset(availParmsSet):
            if len(MadrigalDerivedMethods[key]) >= 4:
                if kinst not in MadrigalDerivedMethods[key][3]:
                    continue # did not pass kinst requirement
                
            # see if this method only requires 1D
            only1D = False
            if inputSet.issubset(avail1DParmsSet):
                only1D = True

            # this method can be derived because all inputs available
            outputParms = MadrigalDerivedMethods[key][1]
            newAvailParms = []
            for parm in outputParms:
                if only1D:
                    if parm not in ret1DList:
                        ret1DList.append(parm)
                        newAvailParms.append(parm)
                else:
                    if parm not in ret2DList:
                        ret2DList.append(parm)
                        newAvailParms.append(parm)
            if len(newAvailParms) > 0:
                if only1D:
                    avail1DParmsSet.update(newAvailParms)
                availParmsSet.update(newAvailParms)
                
    return((ret1DList, ret2DList))


def getUnderivableParms(inputParms, requestedParms):
    """getUnderivableParms returns a set of all parms in requestedParms cannot be derived from requestedParms.
    
    May be empty set
    """
    madParmObj = madrigal.data.MadrigalParameters()
    requestedParmList = [madParmObj.getParmMnemonic(parm) for parm in requestedParms]
    requestParmSet = set(requestedParmList)
    derivableParms = getDerivableParms(inputParms)
    derivableParmSet = set(derivableParms)
    return(requestParmSet.difference(derivableParmSet))



def createBaseMadrigalFileGrid(dtList, latList, lonList, altList, oneDParmDict=None, twoDParmDict=None):
    """createBaseMadrigalFileGrid is a helper method to create a temp Madrigal Hdf5 file to be used in
    running the madCalculatorGrid engine.
    
    Called grid because it creates points at each unique combination of input latitudes, longitudes, and altitudes.
    That is, number of points = len(latList) x len(lonList) x len(altList)
    
    Inputs:
        dtList - a list of datetimes in UT, one for each record.  Length must be one or more.
            
        
        latList - a list of latitudes. May be zero length if a pure 1D calcuation. If one or more
            in length, each value must be unique.
        
        latList - a list of longitudes. May be zero length if a pure 1D calcuation. If one or more
            in length, each value must be unique.  Must be at least length 1 if latList length not 0.
            
        altList - a list of altitudes. May be zero length if a pure 1D calcuation. If one or more
            in length, each value must be unique.  Must be at least length 1 if latList length not 0.
            
        oneDParmDict - dict with keys = lower case one D parm mnemonics, values = parm values.  Length must be
            length of dtList.
            
        twoDParmDict - dict with keys = lower case two D parm mnemonics, values = 4D numpy array of values.  Shape must be
            (length of dtList, len of latList, len of lonList, len of altList).
    """
    tmpFileName = os.path.join(tempfile.gettempdir(), 'tmp_%i.hdf5' % (random.randint(0,999999)))
    cedarFile = madrigal.cedar.MadrigalCedarFile(tmpFileName, createFlag=True)
    if not oneDParmDict is None:
        if 'kinst' in list(oneDParmDict.keys()):
            kinst = int(oneDParmDict['kinst'][0])
            del(oneDParmDict['kinst'])
        else:
            kinst = 31 # random kinst
        if 'kindat' in list(oneDParmDict.keys()):
            kindat = int(oneDParmDict['kindat'][0])
            del(oneDParmDict['kindat'])
        else:
            kindat = 3410 # random kindat
    else:
        kinst = 31 # random kinst
        kindat = 3410 # random kindat
        
    if len(dtList) == 0:
        raise ValueError('dtList cannot be empty')
    
    if len(latList) > 0:
        ind2DList = ['gdlat', 'glon', 'gdalt']
        if len(lonList) == 0 or len(altList) == 0:
            raise ValueError('If latList non-empty, lonList and altList must also not be empty')
        for l in (latList, lonList, altList):
            if len(l) != len(set(l)):
                raise ValueError('Non-unique values found in list %s' % (str(l)))
        num2DRows = len(latList)*len(lonList)*len(altList)
    else:
        if len(lonList) != 0 or len(altList) != 0:
            raise ValueError('If latList empty, lonList and altList must also be empty')
        ind2DList = []
        num2DRows = 1
        
    if oneDParmDict is None:
        oneDParms = []
    else:
        oneDParms = list(oneDParmDict.keys())
    if twoDParmDict is None:
        twoDParms = []
    else:
        twoDParms = list(twoDParmDict.keys())
    if len(latList) > 0:
        twoDParms += ['gdlat', 'glon', 'gdalt']
    
    for i, dt in enumerate(dtList):
        year, month, day, hour, minute, second = dt.year, dt.month, dt.day, \
                                                 dt.hour, dt.minute, dt.second

        newRec = madrigal.cedar.MadrigalDataRecord(kinst, kindat,
                 year, month, day, hour, minute, second, 0,
                 year, month, day, hour, minute, second, 0,
                 oneDParms,
                 twoDParms,
                 num2DRows,
                 ind2DList=ind2DList)
        
        # set all oneD values
        for oneDParm in oneDParms:
            newRec.set1D(oneDParm, oneDParmDict[oneDParm][i])
            
        for twoDParm in twoDParms:
            for j in range(len(latList)):
                for k in range(len(lonList)):
                    for l in range(len(altList)):
                        index = l + k*(len(altList)) + j*(len(altList))*len(lonList)
                        if twoDParm == 'gdlat':
                            newRec.set2D(twoDParm, index, latList[j])
                        elif twoDParm == 'glon':
                            newRec.set2D(twoDParm, index, lonList[k])
                        elif twoDParm == 'gdalt':
                            newRec.set2D(twoDParm, index, altList[l])
                        else:
                            newRec.set2D(twoDParm, index, twoDParmDict[twoDParm][i,j,k,l])
                
        cedarFile.append(newRec)
        
    
    cedarFile.write()
    
    return(tmpFileName)


def createBaseMadrigalFileList(dtList, latList, lonList, altList, oneDParmDict=None, twoDParmDict=None):
    """createBaseMadrigalFileList is a helper method to create a temp Madrigal Hdf5 file to be used in
    running the madCalculatorList engine.
    
    Called list because it creates points at zip(latList, lonList, altList)
    That is, number of points = len(latList)
    
    Inputs:
        dtList - a list of datetimes in UT, one for each record.  Length must be one or more.
            
        
        latList - a list of latitudes. May be zero length if a pure 1D calcuation. 
        
        latList - a list of longitudes. May be zero length if a pure 1D calcuation. Len must = len(latList)
            
        altList - a list of altitudes. May be zero length if a pure 1D calcuation. Len must = len(latList)
            
        oneDParmDict - dict with keys = lower case one D parm mnemonics, values = parm values.  Length must be
            length of dtList.
            
        twoDParmDict - dict with keys = lower case two D parm mnemonics, values numpy float array with shape 
                (len(dtList), len(latList))
    """
    tmpFileName = os.path.join(tempfile.gettempdir(), 'tmp_%i.hdf5' % (random.randint(0,999999)))
    cedarFile = madrigal.cedar.MadrigalCedarFile(tmpFileName, createFlag=True)
    if not oneDParmDict is None:
        if 'kinst' in list(oneDParmDict.keys()):
            kinst = int(oneDParmDict['kinst'][0])
            del(oneDParmDict['kinst'])
        else:
            kinst = 31 # random kinst
        if 'kindat' in list(oneDParmDict.keys()):
            kindat = int(oneDParmDict['kindat'][0])
            del(oneDParmDict['kindat'])
        else:
            kindat = 3410 # random kindat
    else:
        kinst = 31 # random kinst
        kindat = 3410 # random kindat
        
    if len(dtList) == 0:
        raise ValueError('dtList cannot be empty')
    
    if len(latList) > 0:
        ind2DList = ['gdlat', 'glon', 'gdalt']
        num2DRows = len(latList)
    else:
        if len(lonList) != 0 or len(altList) != 0:
            raise ValueError('If latList empty, lonList and altList must also be empty')
        ind2DList = []
        num2DRows = 1
        
    if len(lonList) != len(latList) or len(altList) != len(latList):
        raise ValueError('All position lists must be equal length')
    
        
    if oneDParmDict is None:
        oneDParms = []
    else:
        oneDParms = list(oneDParmDict.keys())
    if twoDParmDict is None:
        twoDParms = []
    else:
        twoDParms = list(twoDParmDict.keys())
    if len(latList) > 0:
        twoDParms += ['gdlat', 'glon', 'gdalt']
    
    for i, dt in enumerate(dtList):
        year, month, day, hour, minute, second = dt.year, dt.month, dt.day, \
                                                 dt.hour, dt.minute, dt.second

        newRec = madrigal.cedar.MadrigalDataRecord(kinst, kindat,
                 year, month, day, hour, minute, second, 0,
                 year, month, day, hour, minute, second, 0,
                 oneDParms,
                 twoDParms,
                 num2DRows,
                 ind2DList=ind2DList)
        
        # set all oneD values
        for oneDParm in oneDParms:
            newRec.set1D(oneDParm, oneDParmDict[oneDParm][i])
            
        for twoDParm in twoDParms:
            for j in range(len(latList)):
                if twoDParm == 'gdlat':
                    newRec.set2D(twoDParm, j, latList[j])
                elif twoDParm == 'glon':
                    newRec.set2D(twoDParm, j, lonList[j])
                elif twoDParm == 'gdalt':
                    newRec.set2D(twoDParm, j, altList[j])
                else:
                    newRec.set2D(twoDParm, j, twoDParmDict[twoDParm][i,j])
                
        cedarFile.append(newRec)
        
    
    cedarFile.write()
    
    return(tmpFileName)
    
    
    


class MadrigalDerivationPlan:
    """MadrigalDerivationPlan is the main class in derivation.  It creates an object that figures out how to create
    new madrigal.cedar.MadrigalDataRecords based on available parms (recordSet),  requested parms, and filters.
    """
    
    def __init__(self, recordSet, requestedParms, filterList=[], madParmObj=None, kinst=None, indParms=None,
                 arraySplitParms=None):
        """__init__ creates a MadrigalDerivationPlan.
        
        Inputs:
        
            recordSet - a numpy recarray with column names lower case mnemonics of the
            parameters in the input cedar file.  The first parameters will always be
            'year', 'month', 'day', 'hour', 'min', 'sec','recno', 'kindat', 'kinst', 
            'ut1_unix', 'ut2_unix'.  Other parameters may follow.  The data type is int64.
            A value of 1 means a one-D parameter, and value of 2 means a dependent
            2D parameter, and a value of 3 means an independent 2D spatial parameter.
            
            requestedParms - the list of lower case mnemonics that are requested to be
            included into the output MadrigalCedarFile
            
            filterList - a list of MadrigalFilter objects to apply to remove data.  Default
            is empty list (no data filtering)
            
            madParmObj - a madrigal.data.MadrigalParameter object.  If None, one will be created.
            
            kinst - if not None, then kinst value may be passed in to for use in methods that are kinst specific.
            If None, then all kinst specific methods are unavailable
            
            indParms - if None, then the new file will not have independent spatial parameters.
                If given, must be the lower case parms with the same length as the number in the original file, and 
                each must be in requestedParms.  May be the same as in original file.
                
            arraySplitParms - if None, no array splitting parameters.  If given, must be lower case parms and
                each must be in requestedParms.
            
        Affects:
            
            The following attributes are created:
            
            self.recordSet - a copy of the input numpy recarray with column names lower case 
                mnemonics of the parameters in the input cedar file.
            
            self.underivableFilterList - a list a filters with parameters that cannot
                be derived from inputs.  Results in immediate return of empty
                MadrigalCedarFile
                
            self.meas1DFilterList - a list of filters that can be applied with only measured
                1D parameters.
                
            self.oneDFilterDict - a dict of key=method name, value = list of 1D filters that
                can be called after that 1D method is executed
                
            self.meas2DFilterList - a list of filters that can be applied with only measured
                2D parameters.
                
            self.twoDFilterDict - a dict of key=method name, value = list of 2D filters that
                can be called after that 2D method is executed
                
            self.oneDMethods - a list of 1D method names required to be executed.  Must contain
                all keys in self.oneDFilterDict
                
            self.twoDMethods - a list of 2D method names required to be executed.  Must contain
                all keys in self.twoDFilterDict
                
            self.requiredParms - an ordered list of all mnemonics to be used in the derivation
                
            self.tempArray - a numpy recarray of type int/string/double with all parameters used
                by all methods.  length is that of self.requiredParms. Used to store data
                during derivation.
                
            self.tempArrayMapDict - a dictionary with keys = method names in self.oneDMethods
                and self.twoDMethods, value is a tuple of two lists of integers 1) the list of indices
                of the positions of the input parameters in self.tempArray for that method, and
                1) the list of indices of the positions of the output parameters in self.tempArray 
                for that method.  These values are used to rapidly map arrays from self.twoDMethods
                to arrays to passed into and read from madrigal._derive
                
            self.requested1D - a set of parameters that can be derived as 1D parms. Always includes
                std parms
            
            self.requested2D - a set of parameters that can be derived as 2D parms
            
            self.requestedNA - a set of parameters that cannot be derived (will be set to 1D)
            
            self.newRecordSet - the recordset for the new MadrigalCedarFile.  Ordered by
                requiredParms, requestedParms
            
            self.datasetDtype - the dataset dtype for the new MadrigalCedarFile. Ordered by
                requiredParms, requestedParms
                
            self.maxInputCount - set to the value of the greatest number of inputs of any
                method to be called.  Used for creating a single numpy array to pass arguments 
                into C methods.
                
            self.maxOutputCount - set to the value of the greatest number of outputs of any
                method to be called.  Used for creating a single numpy array to pass arguments 
                back from C methods.
                
            self.parmObjList - a tuple of three lists: self._oneDList, self._twoDList, and
                self._ind2DList made up of madrigal.cedar.CedarParameter objects.  Passed
                into madrigal.cedar.MadrigalDataRecord inits to speed performance.
            
        """
        if madParmObj is None:
            madParmObj = madrigal.data.MadrigalParameters()
        else:
            madParmObj = madParmObj
            
        self.recordSet = copy.copy(recordSet)
        self.maxInputCount = 0
        self.maxOutputCount = 0
        
        
        self.indParms = indParms
        if not indParms is None:
            # get list of indParm in existing file
            orgIndParms = [parm for parm in recordSet.dtype.names if recordSet[parm] == 3]
            if len(indParms) != len(orgIndParms):
                raise ValueError('indParms passed in <%s> has len %i, but original file had len %i: <s>' \
                    % (str(indParms), len(indParms), len(orgIndParms), str(orgIndParms)))
            for indParm in indParms:
                if indParm not in requestedParms:
                    raise ValueError('indParm %s not in requestedParms' % (indParm))
                
        if not arraySplitParms is None:
            # make sure they are ascii
            newArraySplitParm = []
            for arraySplitParm in arraySplitParms:
                if type(arraySplitParm) in (bytes, numpy.bytes_):
                    newArraySplitParm.append(arraySplitParm.decode("ascii"))
                else:
                    newArraySplitParm.append(arraySplitParm)
            arraySplitParms = newArraySplitParm
        
        self.arraySplitParms = arraySplitParms
        if not arraySplitParms is None:
            for arraySplitParm in arraySplitParms:
                if arraySplitParm not in requestedParms:
                    raise ValueError('arraySplitParm %s not in requestedParms' % (arraySplitParm))
        
        # step one - create a list of all derived methods that are callable because their inputs
        # exist and they create outputs that are new.  Each item in this list is a tuple
        # with values (method name, input set, is1D (bool), new output set
        possibleDerivedMeths = []
        meas1DParms = set(madrigal.cedar.MadrigalDataRecord._stdParms)
        avail1DParms = set(madrigal.cedar.MadrigalDataRecord._stdParms)
        
        file1DParms = [name for name in recordSet.dtype.names if recordSet[name][0] == 1]
        file2DParms = [name for name in recordSet.dtype.names if recordSet[name][0] in (2,3)]
        
        meas1DParms.update(file1DParms) # just in case default were not included
        avail1DParms.update(file1DParms)
        meas2DParms = set(file2DParms)
        avail2DParms = set(file2DParms)
        allAvailParms = avail1DParms.union(avail2DParms)
        
        
        for methodName in list(MadrigalDerivedMethods.keys()):
            inputParms = getLowerCaseSet(MadrigalDerivedMethods[methodName][0])
            outputParms = getLowerCaseSet(MadrigalDerivedMethods[methodName][1])
            
            if len(MadrigalDerivedMethods[methodName]) >= 4:
                if kinst not in MadrigalDerivedMethods[methodName][3]:
                    continue # did not pass kinst requirement
            
            # see if this can be added as a one D method
            if inputParms.issubset(avail1DParms):
                newParms = outputParms.difference(avail1DParms.union(avail2DParms))
                if len(newParms) > 0:
                    possibleDerivedMeths.append([methodName,
                                                 inputParms,
                                                 True,
                                                 newParms,
                                                 outputParms])
                    avail1DParms.update(newParms)
                    allAvailParms.update(newParms)
                continue
            
            # see if this can be added as a two D method
            if inputParms.issubset(allAvailParms):
                newParms = outputParms.difference(allAvailParms)
                if len(newParms) > 0:
                    possibleDerivedMeths.append([methodName,
                                                 inputParms,
                                                 False,
                                                 newParms,
                                                 outputParms])
                    avail2DParms.update(newParms)
                    allAvailParms.update(newParms)
                    
        
        # method loop complete - second step - now deal with filters if any
        self.underivableFilterList = []
        self.meas1DFilterList = []
        self.oneDFilterDict = {}
        self.meas2DFilterList = []
        self.twoDFilterDict = {}
        
        oneDFilterList = [] # filters that will need to be called after 1D derivation methods
        twoDFilterList = [] # filters that will need to be called after 2D derivation methods
        allRequiredFiltParms = set([]) # make sure all filter parms are included
        
        for filter in filterList:
            # all filters will be assigned to one of the above lists
            mnemList = [filter.mnemonic1]
            if filter.mnemonic2 is not None:
                mnemList.append(filter.mnemonic2)
            mnemSet = set(mnemList)
            allRequiredFiltParms.update(mnemSet)
            if len(mnemSet.difference(allAvailParms)) > 0:
                # this filter has an underivable parameter
                self.underivableFilterList.append(filter)
            elif mnemSet.issubset(meas1DParms):
                self.meas1DFilterList.append(filter)
            elif mnemSet.issubset(avail1DParms):
                oneDFilterList.append((filter, mnemSet)) # will be assigned to self.oneDFilterDict later
            elif mnemSet.issubset(meas2DParms):
                self.meas2DFilterList.append(filter)
            else:
                twoDFilterList.append((filter, mnemSet)) # will be assigned to self.twoDFilterDict later
        
        
        # next step - loop backwards through possibleDerivedMeths to fill out all which methods are needed
        self.oneDMethods = []
        self.twoDMethods = []
        requestedSet = getLowerCaseSet(requestedParms)
        self.requested1D = meas1DParms.intersection(requestedParms)
        self.requested1D = self.requested1D.union(madrigal.cedar.MadrigalDataRecord._stdParms)
        self.requested2D = meas2DParms.intersection(requestedParms)
        self.requestedNA = set([])
        allAvailParms = meas1DParms.union(meas2DParms)
        allRequiredParms = self.requested1D.union(self.requested2D, allRequiredFiltParms,
                                                  set(madrigal.cedar.MadrigalDataRecord._stdParms))
        allNeededParms = requestedSet.union(allRequiredFiltParms)
        allUnfullfilledParms = allNeededParms.difference(allAvailParms) # the parameters will still need
        
        for i in range(len(possibleDerivedMeths)-1, -1, -1):
            methodName, inputSet, is1D, newSet, outputParms = possibleDerivedMeths[i]
            newRequiredParms = newSet.intersection(allUnfullfilledParms)
            if len(newRequiredParms) > 0:
                # this method is required - always put first in list
                allUnfullfilledParms = allUnfullfilledParms.difference(newRequiredParms)
                allRequiredParms = allRequiredParms.union(outputParms, inputSet)
                allAvailParms = allAvailParms.union(outputParms)
                # see if any of this methods inputs also need to be derived
                newUnfulfilledParms = inputSet.difference(allAvailParms)
                allUnfullfilledParms = allUnfullfilledParms.union(newUnfulfilledParms)
                if is1D:
                    self.oneDMethods.insert(0, methodName)
                    self.requested1D.update(newSet.intersection(requestedSet))
                else:
                    self.twoDMethods.insert(0, methodName)
                    self.requested2D.update(newSet.intersection(requestedSet))
                    
                # check maximum lengths of argument lists
                if len(MadrigalDerivedMethods[methodName][0]) > self.maxInputCount:
                    self.maxInputCount = len(MadrigalDerivedMethods[methodName][0])
                if len(MadrigalDerivedMethods[methodName][1]) > self.maxOutputCount:
                    self.maxOutputCount = len(MadrigalDerivedMethods[methodName][1])
                    
                
        # determine the requested parms that could not be derived
        self.requestedNA = requestedSet.difference(self.requested1D.union(self.requested2D))
        
        # the final step is to walk forward through self.oneDMethods and self.twoDMethods to determine
        # exactly where the oneDFilterList and twoDFilterList filter (if any) go
        if len(oneDFilterList) or len(twoDFilterList):
            
            # handle 1D
            parmsAvail = meas1DParms
            for methodName in self.oneDMethods:
                newParms = getLowerCaseSet(MadrigalDerivedMethods[methodName][1])
                parmsAvail.update(newParms)
                if len(oneDFilterList):
                    filtersNotRemoved = [] # to keep track of what still needs to be removed
                    for value in oneDFilterList:
                        filter, mnemSet = value
                        if mnemSet.issubset(parmsAvail):
                            # this filter can now be derived
                            if methodName in self.oneDFilterDict:
                                self.oneDFilterDict[methodName].append(filter)
                            else:
                                self.oneDFilterDict[methodName] = [filter]
                        else:
                            filtersNotRemoved.append(value)
                    oneDFilterList = filtersNotRemoved
                    
            if len(twoDFilterList):
                # otherwise we can skip this
                # handle 2D
                parmsAvail.update(meas2DParms)
                for methodName in self.twoDMethods:
                    newParms = getLowerCaseSet(MadrigalDerivedMethods[methodName][1])
                    parmsAvail.update(newParms)
                    if len(twoDFilterList):
                        filtersNotRemoved = [] # to keep track of what still needs to be removed
                        for value in twoDFilterList:
                            filter, mnemSet = value
                            if mnemSet.issubset(parmsAvail):
                                # this filter can now be derived
                                if methodName in self.twoDFilterDict:
                                    self.twoDFilterDict[methodName].append(filter)
                                else:
                                    self.twoDFilterDict[methodName] = [filter]
                            else:
                                filtersNotRemoved.append(value)
                        twoDFilterList = filtersNotRemoved
                        
            # bug check - oneDFilterList and twoDFilterList should both be empty
            if len(oneDFilterList) or len(twoDFilterList):
                raise ValueError('filter %s missed - bug' % str(oneDFilterList + twoDFilterList))
            
        self.requiredParms=self._createSortedParmList(allRequiredParms, requestedParms)
        tempArrDtype = []
        for mnem in self.requiredParms:
            # make sure its utf-8
            if type(mnem) in (bytes, numpy.bytes_):
                mnem = mnem.decode("utf8")
            if madParmObj.isString(mnem):
                width = madParmObj.getStringLen(mnem)
                tempArrDtype.append((mnem, 'S%i' % (width)))
            elif madParmObj.isInteger(mnem):
                tempArrDtype.append((mnem, 'i8'))
            else:
                tempArrDtype.append((mnem, 'f8'))
        self.tempArray = numpy.recarray((1,), dtype=tempArrDtype)

        
        self._createTempArrayMapDict()
        self._createDataTypes(requestedParms, madParmObj)
        self._createCedarParmsLists(madParmObj)
        
        
    def _createTempArrayMapDict(self):
        """_createTempArrayMapDict is the method that creates the indices that allow fast reading
        and writing of data to the temp array self.tempArray.  To be precises, creates:
        
        self.tempArrayMapDict - a dictionary with keys = method names in self.oneDMethods
            and self.twoDMethods, value is a tuple of two lists of integers 1) the list of indices
            of the positions of the input parameters in self.tempArray for that method, and
            1) the list of indices of the positions of the output parameters in self.tempArray 
            for that method.  These values are used to rapidly map arrays from self.twoDMethods
            to arrays to passed into and read from madrigal._derive
        """
        self.tempArrayMapDict = {}
        
        for method in self.oneDMethods + self.twoDMethods:
            inputParms = getLowerCaseList(MadrigalDerivedMethods[method][0])
            outputParms = getLowerCaseList(MadrigalDerivedMethods[method][1])
            inputIndices = [self.requiredParms.index(parm) for parm in inputParms]
            outputIndices = [self.requiredParms.index(parm) for parm in outputParms]
            self.tempArrayMapDict[method] = (inputParms, outputParms, inputIndices, outputIndices)
        
        
    def _createDataTypes(self, requestedParms, madParmObj):
        """_createDataTypes creates self.newRecordSet and self.datasetDtype based on previously
        created attributes
        
        Inputs: requestedParms - the list of lower case mnemonics that are requested to be
            included into the output MadrigalCedarFile. Used for ordering.
            
            madParmObj - a madrigal.data.MadrigalParameter object.
        """
        self.datasetDtype = [] # data type for the Table Layout recarray
        recDType = [] # data type for _record_layout recarray
        recDims = [] # dimension of each parameter (1 for 1D, 2 for dependent 2D, 3 for independent 2D)
        
        # default parms
        for mnem in madrigal.cedar.MadrigalDataRecord._stdParms:
            if madParmObj.isInteger(mnem):
                self.datasetDtype.append((mnem.lower(), int))
            elif madParmObj.isString(mnem):
                strLen = madParmObj.getStringLen(mnem)
                self.datasetDtype.append((mnem.lower(), numpy.str_, strLen))
            else:
                self.datasetDtype.append((mnem.lower(), float))
            recDType.append((mnem.lower(), int))
            recDims.append(1)
            
        # add requestedParms
        for mnem in requestedParms:
            if type(mnem) in (bytes, numpy.bytes_):
                mnem = mnem.decode('utf8')
            if mnem in madrigal.cedar.MadrigalDataRecord._stdParms:
                continue # legal because it may be a default parm
            if madParmObj.isInteger(mnem):
                self.datasetDtype.append((mnem.lower(), int))
            elif madParmObj.isString(mnem):
                strLen = madParmObj.getStringLen(mnem)
                self.datasetDtype.append((mnem.lower(), 'S%i' % (strLen)))
            else:
                self.datasetDtype.append((mnem.lower(), float))
            recDType.append((mnem.lower(), int))
            if mnem in self.requested1D or mnem in self.requestedNA:
                recDims.append(1)
            else:
                value = 2
                if not self.indParms is None:
                    if mnem in self.indParms:
                        value = 3
                recDims.append(value)
            
        self.newRecordSet = numpy.array([tuple(recDims),], dtype = recDType)

        
        
        
    def _createCedarParmsLists(self, madParmObj):
        """_createCedarParmsLists creates the attribute self.parmObjList, which is an object
        passed into madrigal.cedar.MadrigalDataRecord to speed up the init
        
        Input: madParmObj - a madrigal.data.MadrigalParameter object.
        """
        _oneDList = []
        _twoDList = []
        _ind2DList = []
        for parm in self.newRecordSet.dtype.names[len(madrigal.cedar.MadrigalDataRecord._stdParms):]:
            if madParmObj.isInteger(parm):
                isInt = True
            else:
                isInt = False
            newCedarParm = madrigal.cedar.CedarParameter(madParmObj.getParmCodeFromMnemonic(parm),
                                                         parm, madParmObj.getParmDescription(parm),
                                                         isInt)
            if self.newRecordSet[parm][0] == 1:
                _oneDList.append(newCedarParm)
            if self.newRecordSet[parm][0] in (2,3):
                _twoDList.append(newCedarParm)
            if self.newRecordSet[parm][0] == 3:
                _ind2DList.append(newCedarParm)
                
        self.parmObjList = (_oneDList, _twoDList, _ind2DList)
        
        
    def _createSortedParmList(self, allRequiredParms, requestedParms):
        """_createSortedParmList takes the set of allRequiredParms and returns a list, where the order matches that
        of self.datasetDtype in the beginning of the list so that direct copy can be done for speed.
        
        Inputs:
            allRequiredParms - set of all required parms for derivation
            requestedParms - parms wanted for output
        """
        retList = []
        usedMnemList = [] # record which are used already
        for mnem in madrigal.cedar.MadrigalDataRecord._stdParms:
            if mnem not in allRequiredParms:
                raise ValueError('Parm %s not in allRequiredParms' % (mnem))
            retList.append(mnem)
            usedMnemList.append(mnem)
        for mnem in requestedParms:
            mnem = mnem.lower()
            if mnem in madrigal.cedar.MadrigalDataRecord._stdParms:
                continue # legal because it may be a default parm
            retList.append(mnem)
            usedMnemList.append(mnem)
        # add the rest in any order
        for mnem in allRequiredParms:
            mnem = mnem.lower()
            if not mnem in usedMnemList:
                retList.append(mnem)
                
        return(retList)
        
        
        
    def __str__(self):
        retStr = ''
        retStr += 'self.requested1D: %s\n' % (str(self.requested1D))
        retStr += 'self.requested2D: %s\n' % (str(self.requested2D))
        retStr += 'self.requestedNA: %s\n' % (str(self.requestedNA))
        retStr += 'self.oneDMethods: %s\n' % (str(self.oneDMethods))
        retStr += 'self.twoDMethods: %s\n' % (str(self.twoDMethods))
        retStr += 'self.requiredParms:\n'
        for i, parm in enumerate(self.requiredParms):
            retStr += '\t%03i: %s\n' % (i, parm)
        retStr += 'self.tempArray: %s - %s\n' % (str(self.tempArray), str(self.tempArray.dtype))
        retStr += 'self.tempArray.shape %s\n' % (str(self.tempArray.shape))
        retStr += 'self.tempArrayMapDict:\n'
        for key in list(self.tempArrayMapDict.keys()):
            retStr += '\tmethod: %s - %s\n' % (str(key), str(self.tempArrayMapDict[key]))
        
        # filters
        retStr += 'self.oneDFilterDict: %s\n' % (str(self.oneDFilterDict))
        retStr += 'self.twoDFilterDict: %s\n' % (str(self.twoDFilterDict))
        retStr += 'self.meas1DFilterList: %s\n' % (str(self.meas1DFilterList))
        retStr += 'self.meas2DFilterList: %s\n' % (str(self.meas2DFilterList))
        retStr += 'self.underivableFilterList: %s\n' % (str(self.underivableFilterList))
        retStr += 'self.newRecordSet: %s\n' % (str(self.newRecordSet))
        retStr += 'self.datasetDtype: %s\n' % (str(self.datasetDtype))
        retStr += 'self.maxInputCount %i, self.maxOutputCount %i\n' % (self.maxInputCount,
                                                                       self.maxOutputCount)
            
        return(retStr)
        
        
class MadrigalDerivation:
    """MadrigalDerivation is the main class in this module.  It creates a new MadrigalCedarFile based
    on an input MadrigalCedarFile, requestedParms, and input filters
    
    Attributes
        self.madCedarFile - the created new MadrigalCedarFile
    """
    def __init__(self, inMadCedarFile, requestedParms, filterList=[], fullFilename=None,
                 madInstObj=None, madParmObj=None, madMethodsObj=None, madDB=None,
                 indParms=None, arraySplitParms=None):
    
        """Inputs:
            inMadCedarFile - input MadrigalCedarFile object from which to start derivation.
            
            requestedParms - the list of mnemonics that are requested to be
            included into the output MadrigalCedarFile
            
            filterList - a list of MadrigalFilter objects to apply to remove data.  Default
            is empty list (no data filtering)
            
            fullFilename - a file to be created. May also be None (the default) if this
                           data is simply derived parameters that be written to stdout.
                           
            madInstObj - a madrigal.metadata.MadrigalInstrument object.  If None, one will be created.

            madParmObj - a madrigal.data.MadrigalParameter object.  If None, one will be created.
            
            madMethodsObj - a MadrigalDerivationMethods object. If None, one will be created.
            
            madDB - a madrigal.metadata.MadrigalDB object.  If None, one will be created.
            
            indParms - if None, then the new file will not have independent spatial parameters.
                If given, must be the lower case parms with the same length as the number in the original file, and 
                each must be in requestedParms.  May be the same as in original file.
                
            arraySplitParms - if None, no array splitting parameters.  If given, must be lower case parms and
                each must be in requestedParms.
            
        Affects:
            creates self._madCedarFile, which is the new MadrigalCedarFile.  May have zero records if all
            data rejected by filters. Sets self._numRecsAccepted to the total number of records accpeted
            so far
        """
        
        self._inMadCedarFile = inMadCedarFile
        
        # create any needed Madrigal objects, if not passed in
        if madDB is None:
            self._madDB = madrigal.metadata.MadrigalDB()
        else:
            self._madDB = madDB
            
        if madInstObj is None:
            self._madInstObj = madrigal.metadata.MadrigalInstrument(self._madDB)
        else:
            self._madInstObj = madInstObj

        if madParmObj is None:
            self._madParmObj = madrigal.data.MadrigalParameters(self._madDB)
        else:
            self._madParmObj = madParmObj
            
        if madMethodsObj is None:
            self._madMethodsObj = MadrigalDerivationMethods(self._madDB.getMadroot(), 
                                                            self._inMadCedarFile.getEarliestDT())
        else:
            self._madMethodsObj = madMethodsObj
            
        requestedParms = getLowerCaseList(requestedParms)
            
        recordset = self._inMadCedarFile.getRecordset()
        try:
            kinst = self._inMadCedarFile.getKinstList()[0]
        except:
            kinst = None
            
        self.indParms = indParms
        
        self._numRecsAccepted = 0 # total number of records accepted so far
        
        self._madDerivationPlan = MadrigalDerivationPlan(recordset, requestedParms, filterList,
                                                         self._madParmObj, kinst, indParms=indParms,
                                                         arraySplitParms=arraySplitParms)
        
        self._madCedarFile = madrigal.cedar.MadrigalCedarFile(fullFilename, createFlag=True,
                                                              arraySplitParms=arraySplitParms)
        
        if len(self._madDerivationPlan.underivableFilterList) > 0:
            return # accept this error
        
        # the following for loop may be replaced by a map/multiprocessing call
        for rec in  self._inMadCedarFile:
            if rec.getType() == 'data':
                # for the moment a class method, but will use no class attributes so can easily
                # be switched for a map call
                newRec = self._deriveRecord(rec, self._madDerivationPlan)
                if newRec != None:
                    self._madCedarFile.append(newRec)
                    self._numRecsAccepted += 1
                    
        if len(self._madCedarFile) > 0:
            self._madCedarFile.updateMinMaxParmDict()
        
        
        
    def loadRecords(self, maxRecords):
        """loadRecords loads more records into self._madCedarFile
        
        Returns a tuple of (number of records loaded from the input file this time, isComplete boolean).
        """
        numRecs, isComplete = self._inMadCedarFile.loadNextRecords(maxRecords)
     
        # the following for loop may be replaced by a map/multiprocessing call
        for rec in  self._inMadCedarFile:
            if rec.getType() == 'data':
                # for the moment a class method, but will use no class attributes so can easily
                # be switched for a map call
                newRec = self._deriveRecord(rec, self._madDerivationPlan)
                if newRec != None:
                    self._madCedarFile.append(newRec)
                    self._numRecsAccepted += 1
                    
        if len(self._madCedarFile) > 0:
            self._madCedarFile.updateMinMaxParmDict()
            
        return((numRecs, isComplete))
        
                    
                                        
                    
    def getNewCedarFile(self):
        """getNewCedarFile returns the created MadrigalCedarFile
        """
        return(self._madCedarFile)
    
    
    def getNumRecsAccepted(self):
        """getNumRecsAccepted returned the total number of records so far that passed all filters
        """
        return(self._numRecsAccepted)
                    
                    
    
    def _deriveRecord(self, madDataRec, madDerPlan):
        """_deriveRecord is a method that creates a single MadrigalDataRecord based on an input
        record and a madDerivationPlan
        
        Inputs:
            madDataRec - a madrigal.cedar.MadrigalDataRecord from the input file
            
            madDerPlan - the MadrigalDerivationPlan to apply
        """
        dataset = madDataRec.getDataset() # input measured data
        inputArr = numpy.zeros((madDerPlan.maxInputCount,), dtype='f8') # used to pass in arg to _derive
        outputArr = numpy.zeros((madDerPlan.maxOutputCount,), dtype='f8') # used to pass in arg to _derive
        # step one - fill out madDerPlan.tempArray with all measured parms so we can apply
        # any filters in madDerPlan.meas1DFilterList
        for mnem in madDerPlan.recordSet.dtype.names:
            if mnem in madDerPlan.requiredParms: # and not self._madParmObj.isString(mnem):
                madDerPlan.tempArray[mnem] = dataset[mnem][0]
        for filter in madDerPlan.meas1DFilterList:
            if not self._callFilter(filter, madDerPlan):
                return(None)
            
        # step 2 - call all needed 1D methods.  After each, check if there are any more 1D filters to call
        for methodName in madDerPlan.oneDMethods:
            # first check if its a C or python method
            if len(MadrigalDerivedMethods[methodName]) == 2:
                isC = True
            elif MadrigalDerivedMethods[methodName][2] == 'C':
                isC = True
            else:
                isC = False

            inParms, outParms, inIndices, outIndices = madDerPlan.tempArrayMapDict[methodName]
            for i, inParm in enumerate(inParms):
                try:
                    inputArr[i] = madDerPlan.tempArray[inParm] 
                except:
                    # should be exactly 1 item (scalar)
                    inputArr[i] = madDerPlan.tempArray[inParm][0]

            # check for Nan in inputs
            if numpy.any(numpy.isnan(inputArr[:len(inIndices)])):
                outputArr[:len(outIndices)] = numpy.nan
                
            else:
                # call either C or Python derivation engine
                if isC:
                    # C method
                    madrigal._derive.madDispatch(methodName, inputArr, outputArr)
                else:
                    # python method
                    self._madMethodsObj.dispatchPython(methodName, inputArr, outputArr)
                
            for i in range(len(outIndices)):
                madDerPlan.tempArray[outParms[i]] = outputArr[i]
            
            # see if there is one or more 1D filters to call
            if methodName in madDerPlan.oneDFilterDict:
                for filter in madDerPlan.oneDFilterDict[methodName]:
                    if not self._callFilter(filter, madDerPlan):
                        return(None)
                    
        # step 3 - if there no are 2D parameters requested, create a MadrigalDataRecord and return
        if len(madDerPlan.requested2D) == 0:
            new_dataset = numpy.recarray((1,), dtype=madDerPlan.datasetDtype)
            for parm in madDerPlan.requested1D:
                new_dataset[parm] = madDerPlan.tempArray[parm]
            if len(madDerPlan.requestedNA) > 0:
                for badParm in madDerPlan.requestedNA:
                    # we need to get data type
                    for i, value in enumerate(madDerPlan.datasetDtype):
                        if value[0] == badParm:
                            if value[1] == float:
                                new_dataset[badParm] = numpy.nan
                            elif value[1]  in (int, int):
                                new_dataset[badParm] = -9999
                            elif value[1] is numpy.string_:
                                new_dataset[badParm] = '?'
                                
                        
            newDataRec = madrigal.cedar.MadrigalDataRecord(dataset=new_dataset,
                                                           recordSet=madDerPlan.newRecordSet,
                                                           madInstObj=self._madInstObj,
                                                           madParmObj=self._madParmObj,
                                                           parmObjList=madDerPlan.parmObjList)
            return(newDataRec)
        
        # step 4 - start loop through existing 2D records
        new_dataset = None
        for i in range(madDataRec.getNrow()):
                        
            # step 4.1 - fill in all required measured data for this row
            if i != 0: # skip first row because it was already populated for 1D work
                for mnem in madDerPlan.recordSet.dtype.names:
                    if mnem in madDerPlan.requiredParms:
                        madDerPlan.tempArray[mnem] = dataset[mnem][i]
            
            # step 4.2 - call any 2D filters that do not require derived parms
            passedAll = True
            for filter in madDerPlan.meas2DFilterList:
                if not self._callFilter(filter, madDerPlan):
                    passedAll = False
                    break # this row rejected - no sense continuing
                
            if not passedAll:
                continue
                
            # set 4.3 - call all required 2D methods, and any associated filters afterwards
            for methodName in madDerPlan.twoDMethods:
                # first check if its a C or python method
                if len(MadrigalDerivedMethods[methodName]) == 2:
                    isC = True
                elif MadrigalDerivedMethods[methodName][2] == 'C':
                    isC = True
                else:
                    isC = False
                inParms, outParms, inIndices, outIndices = madDerPlan.tempArrayMapDict[methodName]
                for i, inParm in enumerate(inParms):
                    try:
                        inputArr[i] = float(madDerPlan.tempArray[inParm])
                    except:
                        # should be exactly 1 item (scalar)
                        inputArr[i] = float(madDerPlan.tempArray[inParm][0])
                
                # check for Nan in inputs
                if numpy.any(numpy.isnan(inputArr[:len(inIndices)])):
                    outputArr[:len(outIndices)] = numpy.nan
                    
                else:
                    # call either C or Python derivation engine
                    if isC:
                        # C method
                        madrigal._derive.madDispatch(methodName, inputArr, outputArr)
                    else:
                        # python method
                        self._madMethodsObj.dispatchPython(methodName, inputArr, outputArr)
                
                for i in range(len(outIndices)):
                    madDerPlan.tempArray[outParms[i]] = outputArr[i]
                
                # see if there is one or more 2D filters to call
                if methodName in madDerPlan.twoDFilterDict:
                    for filter in madDerPlan.twoDFilterDict[methodName]:
                        if not self._callFilter(filter, madDerPlan):
                            passedAll = False
                            break # this row rejected - no sense continuing
                        
                if not passedAll:
                    break # this row rejected - no sense continuing
                
            if not passedAll:
                continue # this row rejected
                        
            # if we made it to here, then this is a new row to add to the dataset
            if new_dataset is None:
                new_dataset = numpy.recarray((1,), dtype=madDerPlan.datasetDtype)
                for parm in madDerPlan.requested1D: # get the 1D data just for the first row
                    new_dataset[parm] = madDerPlan.tempArray[parm]
            else:
                new_dataset.resize((len(new_dataset)+1,))
                
            for parm in madDerPlan.requested2D:
                if not self._madParmObj.isString(parm):
                    try:
                        new_dataset[parm][-1] = madDerPlan.tempArray[parm]
                    except:
                        # treat this value like a scalar, not array
                        # double check that it is a single value
                        if (madDerPlan.tempArray[parm].ndim == 1) and (len(madDerPlan.tempArray[parm]) == 1):
                            new_dataset[parm][-1] = madDerPlan.tempArray[parm][0]
                else:
                    new_dataset[parm][-1] = madDerPlan.tempArray[parm][-1]
            
                
        # done looping over all the rows - check if any passed
        if new_dataset is None:
            # no rows made it through the 2D filters
            return(None)
        
        # now we need to copy all the 1D data from the first row to the rest of the rows
        for parm in madDerPlan.requested1D:
            new_dataset[parm][:] = new_dataset[parm][0]
            
        # set all the underivable parms to nan or -9999
        if len(madDerPlan.requestedNA) > 0:
            for badParm in madDerPlan.requestedNA:
                # we need to get data type
                for i, value in enumerate(madDerPlan.datasetDtype):
                    if value[0] == badParm:
                        if value[1] == float:
                            new_dataset[badParm][:] = numpy.nan
                        elif value[1]  in (int, int):
                            new_dataset[badParm][:] = -9999
                        elif value[1] is numpy.string_:
                            new_dataset[badParm] = '?'
            
        # create MadrigalDataRecord to return
        newDataRec = madrigal.cedar.MadrigalDataRecord(dataset=new_dataset,
                                                       recordSet=madDerPlan.newRecordSet,
                                                       madInstObj=self._madInstObj,
                                                       madParmObj=self._madParmObj,
                                                       parmObjList=madDerPlan.parmObjList,
                                                       ind2DList=self.indParms)
        
        return(newDataRec)
    
    
    def _callFilter(self, filter, madDerPlan):
        """_callFilter calls a specific filter and returns True if pass, False if fail
        
        Inputs:
            filter - the MadrigalFilter object to call
            madDerPlan - the MadrigalDerivationPlan being used
        """
        if filter.mnemonic2 is not None:
            result = filter.filter(madDerPlan.tempArray[filter.mnemonic1],
                                   madDerPlan.tempArray[filter.mnemonic2])
        else:
            result = filter.filter(madDerPlan.tempArray[filter.mnemonic1])

        return(result)
    
        
            
        
    
class MadrigalFilter:
    """MadrigalFilter is a class that holds all information about a filter being applied
    
    Attributes
        mnemonic1 - first mnemonic used in filter in std form
        mnemonic2 - second mnemonic.  May be None.  Only not None when filter is mnem1 [+-*/]
        operator - the operator to apply between mnemonic1 and mnemonic2.  None if mnemonic2 is None.
            Must be in ('+', '-', '*', '/') if not None
        rangeList - a list of lower and upper values.  Values must be float or nan.  Nan limits are ignored
            unless derived value is Nan.
        mnem1IsError - True if mnemonic1 is an error parameter, False otherwise.
        mnem2IsError - True if mnemonic2 is an error parameter, False is not, None if mnemonic2 is None.
    """
    def __init__(self, mnemonic1, rangeList, madParmObj=None, mnemonic2=None, operator=None):
        """Inputs:
        
            mnemonic1 - first mnemonic used in filter in std form
            rangeList - a list of lower and upper values.  Values must be float or nan.  Nan limits are ignored
                unless derived value is Nan.
            madParmObj - a madrigal.data.MadrigalParameters object.  Used to determine if parameters are error parms.
                Created if None passed in.
            mnemonic2 - second mnemonic.  May be None.  Only not None when filter is mnem1 [+-*/]
            operator - the operator to apply between mnemonic1 and mnemonic2.  None if mnemonic2 is None.
                Must be in ('+', '-', '*', '/') if not None
        """
        if madParmObj is None:
            madParmObj = madrigal.data.MadrigalParameters()
            
        self.mnemonic1 = mnemonic1.lower()
        if madParmObj.isError(mnemonic1):
            self.mnem1IsError = True
        else:
            self.mnem1IsError = False
        self.rangeList = rangeList
        # verify valid
        for thisRange in self.rangeList:
            if len(thisRange) != 2:
                raise ValueError('Each range in rangeList must have two items - lower and upper, not <%s>' % (str(thisRange)))
            try:
                math.isnan(thisRange[0])
                math.isnan(thisRange[1])
            except:
                raise ValueError('Lower and upper values must be numbers or nan, not <%s %s>' % (str(thisRange[0]), 
                                                                                                  str(thisRange[1])))
        if mnemonic2 is not None:
            self.mnemonic2 = mnemonic2.lower()
        else:
            self.mnemonic2 = mnemonic2
        if mnemonic2 is None:
            self.mnem2IsError = None
        else:
            if madParmObj.isError(mnemonic2):
                self.mnem2IsError = True
            else:
                self.mnem2IsError = False
        if operator not in ('+', '-', '*', '/', None):
            raise ValueError('operator must be one of +, -, /, *, None, not <%s>' % (str(operator)))
        if operator is None and self.mnemonic2 is not None:
            raise ValueError('operator must not be None is mnemonic2 is not None.')
        self.operator = operator
        
        
    def filter(self, mnem1Value, mnem2Value=None):
        """filter returns True or False depending on whether value(s) are accepted by the filter
        
        Inputs:
            mnem1Value - value to test.  Must be a number or Nan.
            
            mnem2Value - None if no second mnemonic.  If there is a second mnemonic
        """
        
        # first step is to see if we can return False immediately based on invalid values
        if type(mnem1Value) not in (math.nan, numpy.nan, float, int):
            # mmem1value is array type 
            mnem1Value = mnem1Value[0]
        if math.isnan(mnem1Value):
            return(False)
        if self.mnem1IsError and mnem1Value < 0.0:
            # no valid error value below zero, and all special values are automatically rejected
            return(False)
        
        if not self.mnemonic2 is None:
            if math.isnan(mnem2Value):
                return(False)
            if self.mnem2IsError and mnem2Value < 0.0:
                # no valid error value below zero, and all special values are automatically rejected
                return(False)
            
            # we need to calculate a new value
            if self.operator == '+':
                value = mnem1Value + mnem2Value
            elif self.operator == '-':
                value = mnem1Value - mnem2Value
            elif self.operator == '*':
                value = mnem1Value * mnem2Value
            elif self.operator == '/':
                # protect again zero division
                if mnem2Value == 0.0:
                    return(False)
                value = mnem1Value / mnem2Value
                
        else:
            value = mnem1Value
            
        # finally search the ranges - if any are okay, return True
        for lower, upper in self.rangeList:
            if math.isnan(lower) and math.isnan(upper):
                # all values pass this
                return(True)
            elif math.isnan(lower) and value <= upper:
                return(True)
            elif math.isnan(upper) and value >= lower:
                return(True)
            elif value >= lower and value <= upper:
                return(True)
            
        # no ranges matched
        return(False)
    
    def __repr__(self):
        """"__repr__ formats the filter as expected in the isprint summary
        """
        if not self.mnemonic2 is None:
            retStr = '    %s %s %s\n' % (self.mnemonic1.upper(),
                                         self.operator,
                                         self.mnemonic2.upper())
        else:
            retStr = '    %s\n' % (self.mnemonic1.upper())
        for i, values in enumerate(self.rangeList):
            lower, upper = values
            if math.isnan(lower):
                lowerStr = 'no lower limit'
            else:
                lowerStr = 'Lower = %s' % (str(lower))
            if math.isnan(upper):
                upperStr = 'no upper limit'
            else:
                upperStr = 'upper = %s' % (str(upper))
            retStr += '    Range %i: %s, %s\n' % (i+1, lowerStr, upperStr)
            
        return(retStr)
    
    
class MadrigalDerivationMethods:
    """MadrigalDerivationMethods is a class that directly calls derivation methods without going through a C library.
    
    For now, covers all calls to get geophysical parameters
    """
    
    def __init__(self, madroot, firstDT=None):
        """__init__ creates a MadrigalDerivationMethods class.  It increases performance of geophysical data lookup
        by taking advantage of the fact that the times data is requested is usually close together.  So when the first call is
        made, data is cached plus and minus a few weeks in either direction.  This speeds up lookups.  If a request goes
        outside the cache, the cache is dumped and a new one created.
        
        If firstDT not None, then getFirstTime succeeds
        
        Creates attributes:
        
            madroot - madroot variable = used to find geo files
            
            firstDT - first datetime in file.  None if not passed in.
            
            madInst - madrigal.metadata.MadrigalInstrument object
        
            geoTable - a subset around the requested time of the Table from the geo file.  
                Default is None - opened only when getGeo called.
                
            startGeoUT, endGeoUT - the start and end unix ut times of the available geoTable
                Default is None - set only when getGeo called.
                
            dstTable - a subset around the requested time of the Table from the dst file.  
                Default is None - opened only when getDst called.
                
            startDstUT, endDstUT - the start and end unix ut times of the available dstTable.
                Default is None - set only when getDst called.
            
            imfTable - a subset around the requested time of the Table from the imf file.  
                Default is None - opened only when getImf called.
                
            startImfUT, endImfUT - the start and end unix ut times of the available imfTable.
                Default is None - set only when getImf called.
            
            fof2Table - a subset around the requested time of the Table from the Millstone fof2 file.  
                Default is None - opened only when getFof2 called.
                
            startFof2UT, endFof2UT - the start and end unix ut times of the available fof2Table.
                Default is None - set only when getFof2 called.
                
            lastUT1_Unix_iri - used to see if cached iri geophysical data can be reused
            
            iri_iap3 - cache of ap3 values for iri call
            
            iri_f107 - cache of f107 value for iri call
            
            lastUT1_Unix_msis - used to see if cached msis geophysical data can be reused
            
            msis_ap - cache of msis ap array
            
            msis_fbar - cache of msis fbar
            
            msis_f107 - cache of msis f107
            
            lastUT1_Unix_tsygan - used to see if cached Tsyganenko geophysical data can be reused
            
            tsygan_swspd - cache of tsygan swspd array
            
            tsygan_ygsm_now - cache of tsygan ygsm value
            
            tsygan_zgsm - cache of tsygan zgsm array
            
            tsygan_swden - cache of tsygan swden array
            
            tsygan_dst - cache of tsygan dst value
            
        """
        self.madroot = madroot
        
        self.firstDT = firstDT
        
        self.madInst = madrigal.metadata.MadrigalInstrument()
        
        self.geoTable = None
        self.startGeoUT = None
        self.endGeoUT = None
        
        self.dstTable = None
        self.startDstUT = None
        self.endDstUT = None
        
        self.imfTable = None
        self.startImfUT = None
        self.endImfUT = None
        
        self.fof2Table = None
        self.startFof2UT = None
        self.endFof2UT = None
        
        self.numSecsToCache = 3600*24*14 # two weeks
        
        # iri cache
        self.lastUT1_Unix_iri = None
        self.iri_iap3 = None
        self.iri_f107 = None
        
        # msis cache
        self.lastUT1_Unix_msis = None
        self.msis_ap = None
        self.msis_fbar = None
        self.msis_f107 = None
        
        # tsygan cache
        self.lastUT1_Unix_tsygan = None
        self.tsygan_swspd = None
        self.tsygan_ygsm_now = None
        self.tsygan_zgsm = None
        self.tsygan_swden = None
        self.tsygan_dst = None
        
        
    def dispatchPython(self, methodName, inputArr, outputArr):
        """dispatchPython is the method called to run any of the derivation methods available through this class.
        
        Inputs:
            methodName - name of the method to call
            
            inputArr - numpy f8 array of input values.  
            
            outputArr - numpy f8 array of output values to set
        """
        if methodName == 'getStation':
            self.getStation(inputArr, outputArr)
        elif methodName == 'getGeo':
            self.getGeo(inputArr, outputArr)
        elif methodName == 'getDst':
            self.getDst(inputArr, outputArr)
        elif methodName == 'getImf':
            self.getImf(inputArr, outputArr)
        elif methodName == 'getFof2Mlh':
            self.getFof2Mlh(inputArr, outputArr)
        elif methodName == 'getNeNe8':
            self.getNeNe8(inputArr, outputArr)
        elif methodName == 'getDNeDNe8':
            self.getDNeDNe8(inputArr, outputArr)
        elif methodName == 'getIri':
            self.getIri(inputArr, outputArr)
        elif methodName == 'getVisrNe':
            self.getVisrNe(inputArr, outputArr)
        elif methodName == 'getVisrTe':
            self.getVisrTe(inputArr, outputArr)
        elif methodName == 'getVisrTi':
            self.getVisrTi(inputArr, outputArr)
        elif methodName == 'getVisrVo':
            self.getVisrVo(inputArr, outputArr)
        elif methodName == 'getVisrHNMax':
            self.getVisrHNMax(inputArr, outputArr)
        elif methodName == 'getNeut':
            self.getNeut(inputArr, outputArr)
        elif methodName == 'getTsygan':
            self.getTsygan(inputArr, outputArr)
        elif methodName == 'getFirstTime':
            self.getFirstTime(inputArr, outputArr)
        elif methodName == 'getAacgm':
            self.getAacgm(inputArr, outputArr)
        elif methodName == 'fromAacgm':
            self.fromAacgm(inputArr, outputArr)
        elif methodName == 'getB_up':
            self.getB_up(inputArr, outputArr)
        elif methodName == 'getBd':
            self.getBd(inputArr, outputArr)
        elif methodName == 'getDiff_B_up':
            self.getDiff_B_up(inputArr, outputArr)
        elif methodName == 'getDiff_Bd':
            self.getDiff_Bd(inputArr, outputArr)
        elif methodName == 'getGeod':
            self.getGeod(inputArr, outputArr)
        elif methodName == 'getDGeod':
            self.getDGeod(inputArr, outputArr)
        elif methodName == 'getGeodGdalt':
            self.getGeodGdalt(inputArr, outputArr)
        elif methodName == 'getGeodAlt':
            self.getGeodAlt(inputArr, outputArr)
        elif methodName == 'getAzElRange':
            self.getAzElRange(inputArr, outputArr)
        else:
            raise ValueError('method %s not implemented' % (methodName))
        
    
    # method implementations
    
    def getStation(self, inputArr, outputArr):
        """getStation modifies the outputArr with the values of:
        
            "GDLATR", "GDLONR", "GALTR"
            
            given an inputArr with:
            
            "KINST"
        """
        kinst = int(inputArr[0])
        gdlatr = self.madInst.getLatitude(kinst)
        gdlonr = self.madInst.getLongitude(kinst)
        galtr = self.madInst.getAltitude(kinst)
        for i, item in enumerate((gdlatr, gdlonr, galtr)):
            if item is None:
                outputArr[i] = 0.0
            else:
                outputArr[i] = item
        
    
    def getGeo(self, inputArr, outputArr):
        """getGeo modifies the outputArr with the values of:
        
            "KP", "AP3", "AP", "F10.7", "FBAR"
            
            given an inputArr with:
            
            "UT1_UNIX", "UT2_UNIX"
        """
        dataFile = 'experiments/1950/gpi/01jan50/geo500101g.002.hdf5'
        
        aveUT = (inputArr[0] + inputArr[1])/2.0
        
        if self.geoTable is None:
            # first need to open file
            filename = os.path.join(self.madroot, dataFile)
            try:
                f = h5py.File(filename, 'r')
                self.geoTable = f['Data']['Table Layout']
                self.startGeoUT = self.geoTable['ut1_unix'][0]
                self.endGeoUT = self.geoTable['ut1_unix'][-1]
                if aveUT < self.startGeoUT or aveUT > self.endGeoUT:
                    raise ValueError('')
                
                # get cache
                cond1 = numpy.where(self.geoTable['ut1_unix'] > aveUT - self.numSecsToCache)
                cond2 = numpy.where(self.geoTable['ut1_unix'] < aveUT + self.numSecsToCache)
                selection = numpy.intersect1d(cond1, cond2)
                self.geoTable = numpy.array(self.geoTable[selection.tolist()])
                if len(self.geoTable) == 0:
                    raise ValueError('')
                f.close()
            except:
                try:
                    f.close()
                except:
                    pass
                outputArr[:5] = numpy.nan
                return
            
            
        # check that data is available
        if aveUT < self.startGeoUT or aveUT > self.endGeoUT:
            outputArr[:5] = numpy.nan
            return
        
        # check if cache needs to be updated
        updateNeeded = False
        try:
            if len(self.geoTable) == 0:
                updateNeeded = True 
            elif (aveUT < self.geoTable['ut1_unix'][0] or aveUT > self.geoTable['ut1_unix'][-1]):
                updateNeeded = True
        except ValueError:
            updateNeeded = True
        if updateNeeded:
            # this is not expected to fail
            filename = os.path.join(self.madroot, dataFile)
            f = h5py.File(filename, 'r')
            self.geoTable = f['Data']['Table Layout']
            cond1 = numpy.where(self.geoTable['ut1_unix'] > aveUT - self.numSecsToCache)
            cond2 = numpy.where(self.geoTable['ut1_unix'] < aveUT + self.numSecsToCache)
            selection = numpy.intersect1d(cond1, cond2)
            self.geoTable = numpy.array(self.geoTable[selection.tolist()])
            f.close()
            if len(self.geoTable) == 0:
                outputArr[:5] = numpy.nan
                return
            
        # find out where this value fits
        index = numpy.searchsorted(self.geoTable['ut1_unix'], [aveUT])[0]
        if index == 0:
            outputArr[:5] = numpy.nan
            return
        
        correctRow = None
        if aveUT - self.geoTable['ut1_unix'][index-1] <= 10800.0: # three hours - the spacing of data in file
            correctRow = self.geoTable[index-1]
        else:
            outputArr[:5] = numpy.nan
            return
        
        outputArr[0] = correctRow['kp']
        outputArr[1] = correctRow['ap3']
        outputArr[2] = correctRow['ap']
        outputArr[3] = correctRow['f10.7']
        outputArr[4] = correctRow['fbar']
        
        return
    
    
    def getDst(self, inputArr, outputArr):
        """getDst modifies the outputArr with the values of:
        
            "DST"
            
            given an inputArr with:
            
            "UT1_UNIX", "UT2_UNIX"
        """
        dataFile = 'experiments/1957/dst/01jan57/dst570101g.002.hdf5'
        
        aveUT = (inputArr[0] + inputArr[1])/2.0
        
        if self.dstTable is None:
            # first need to open file
            filename = os.path.join(self.madroot, dataFile)
            try:
                f = h5py.File(filename, 'r')
                self.dstTable = f['Data']['Table Layout']
                self.startDstUT = self.dstTable['ut1_unix'][0]
                self.endDstUT = self.dstTable['ut1_unix'][-1]
                if aveUT < self.startDstUT or aveUT > self.endDstUT:
                    raise ValueError('')
                
                # get cache
                cond1 = numpy.where(self.dstTable['ut1_unix'] > aveUT - self.numSecsToCache)
                cond2 = numpy.where(self.dstTable['ut1_unix'] < aveUT + self.numSecsToCache)
                selection = numpy.intersect1d(cond1, cond2)
                self.dstTable = numpy.array(self.dstTable[selection.tolist()])
                if len(self.dstTable) == 0:
                    raise ValueError('')
                f.close()
            except:
                try:
                    f.close()
                except:
                    pass
                outputArr[:1] = numpy.nan
                return
            
            
        # check that data is available
        if aveUT < self.startDstUT or aveUT > self.endDstUT:
            outputArr[:1] = numpy.nan
            return
        
        # check if cache needs to be updated
        updateNeeded = False
        try:
            if len(self.dstTable) == 0:
                updateNeeded = True 
            elif (aveUT < self.dstTable['ut1_unix'][0] or aveUT > self.dstTable['ut1_unix'][-1]):
                updateNeeded = True
        except ValueError:
            updateNeeded = True
        if updateNeeded:
            filename = os.path.join(self.madroot, dataFile)
            f = h5py.File(filename, 'r')
            self.dstTable = f['Data']['Table Layout']
            cond1 = numpy.where(self.dstTable['ut1_unix'] > aveUT - self.numSecsToCache)
            cond2 = numpy.where(self.dstTable['ut1_unix'] < aveUT + self.numSecsToCache)
            selection = numpy.intersect1d(cond1, cond2)
            self.dstTable = numpy.array(self.dstTable[selection.tolist()])
            f.close()
            if len(self.dstTable) == 0:
                outputArr[:1] = numpy.nan
                return
            
        # find out where this value fits
        index = numpy.searchsorted(self.dstTable['ut1_unix'], [aveUT])[0]
        if index == 0:
            outputArr[:1] = numpy.nan
            return
        
        correctRow = None
        if aveUT - self.dstTable['ut1_unix'][index-1] <= 3600.0: # one hour - the spacing of data in file
            correctRow = self.dstTable[index-1]
        else:
            outputArr[:1] = numpy.nan
            return

        outputArr[0] = correctRow['dst']
        
        return
    
    
    def getImf(self, inputArr, outputArr):
        """getDst modifies the outputArr with the values of:
        
            "BXGSM", "BYGSM", "BZGSM", "BIMF",
            "BXGSE", "BYGSE", "BZGSE",
            "SWDEN", "SWSPD", "SWQ"
            
            given an inputArr with:
            
            "UT1_UNIX", "UT2_UNIX"
        """
        dataFile = 'experiments/1963/imf/27nov63/imf631127g.002.hdf5'
        
        aveUT = (inputArr[0] + inputArr[1])/2.0
        
        if self.imfTable is None:
            # first need to open file
            filename = os.path.join(self.madroot, dataFile)
            try:
                f = h5py.File(filename, 'r')
                self.imfTable = f['Data']['Table Layout']
                self.startImfUT = self.imfTable['ut1_unix'][0]
                self.endImfUT = self.imfTable['ut1_unix'][-1]
                if aveUT < self.startImfUT or aveUT > self.endImfUT:
                    raise ValueError('')
                
                # get cache
                cond1 = numpy.where(self.imfTable['ut1_unix'] > aveUT - self.numSecsToCache)
                cond2 = numpy.where(self.imfTable['ut1_unix'] < aveUT + self.numSecsToCache)
                selection = numpy.intersect1d(cond1, cond2)
                self.imfTable = numpy.array(self.imfTable[selection.tolist()])
                if len(self.imfTable) == 0:
                    raise ValueError('')
                f.close()
            except:
                try:
                    f.close()
                except:
                    pass
                outputArr[:10] = numpy.nan
                return
            
            
        # check that data is available
        if aveUT < self.startImfUT or aveUT > self.endImfUT:
            outputArr[:10] = numpy.nan
            return
        
        # check if cache needs to be updated
        updateNeeded = False
        try:
            if len(self.imfTable) == 0:
                updateNeeded = True 
            elif (aveUT < self.imfTable['ut1_unix'][0] or aveUT > self.imfTable['ut1_unix'][-1]):
                updateNeeded = True
        except ValueError:
            updateNeeded = True
        if updateNeeded:
            filename = os.path.join(self.madroot, dataFile)
            f = h5py.File(filename, 'r')
            self.imfTable = f['Data']['Table Layout']
            cond1 = numpy.where(self.imfTable['ut1_unix'] > aveUT - self.numSecsToCache)
            cond2 = numpy.where(self.imfTable['ut1_unix'] < aveUT + self.numSecsToCache)
            selection = numpy.intersect1d(cond1, cond2)
            self.imfTable = numpy.array(self.imfTable[selection.tolist()])
            f.close()
            if len(self.imfTable) == 0:
                outputArr[:10] = numpy.nan
                return
            
        # find out where this value fits
        index = numpy.searchsorted(self.imfTable['ut1_unix'], [aveUT])[0]
        if index == 0:
            outputArr[:10] = numpy.nan
            return
        
        correctRow = None
        if aveUT - self.imfTable['ut1_unix'][index-1] <= 3600.0: # one hour - the spacing of data in file
            correctRow = self.imfTable[index-1]
        else:
            outputArr[:10] = numpy.nan
            return

        outputArr[0] = correctRow['bxgsm']
        outputArr[1] = correctRow['bygsm']
        outputArr[2] = correctRow['bzgsm']
        outputArr[3] = math.sqrt(math.pow(correctRow['bxgsm'], 2) + \
                                 math.pow(correctRow['bygsm'], 2) + \
                                 math.pow(correctRow['bzgsm'], 2)) # square root of sum of squares
        outputArr[4] = correctRow['bxgsm'] # bxgse equals bxgsm
        outputArr[5] = correctRow['bygse']
        outputArr[6] = correctRow['bzgse']
        outputArr[7] = correctRow['swden']
        outputArr[8] = correctRow['swspd']
        outputArr[9] = correctRow['swq']
        
        return
    
    
    
    def getFof2Mlh(self, inputArr, outputArr):
        """getFof2Mlh modifies the outputArr with the values of:
        
            "FOF2_MLH"
            
            given an inputArr with:
            
            "UT1_UNIX", "UT2_UNIX", "KINST"
        """
        dataFile = 'experiments/1976/uld/03dec76/uld761203g.002.hdf5'
        
        aveUT = (inputArr[0] + inputArr[1])/2.0
        
        if not inputArr[2] in [30,31,32,5340,5360]:
            # only applies to Millstone ISR
            outputArr[:1] = numpy.nan
            return
        
        if self.fof2Table is None:
            # first need to open file
            filename = os.path.join(self.madroot, dataFile)
            try:
                f = h5py.File(filename, 'r')
                self.fof2Table = f['Data']['Table Layout']
                self.startFof2UT = self.fof2Table['ut1_unix'][0]
                self.endFof2UT = self.fof2Table['ut1_unix'][-1]
                if aveUT < self.startFof2UT or aveUT > self.endFof2UT:
                    raise ValueError('')
                
                # get cache
                cond1 = numpy.where(self.fof2Table['ut1_unix'] > aveUT - self.numSecsToCache)
                cond2 = numpy.where(self.fof2Table['ut1_unix'] < aveUT + self.numSecsToCache)
                selection = numpy.intersect1d(cond1, cond2)
                self.fof2Table = numpy.array(self.fof2Table[selection.tolist()])
                if len(self.fof2Table) == 0:
                    raise ValueError('')
                f.close()
            except:
                try:
                    f.close()
                except:
                    pass
                outputArr[:1] = numpy.nan
                return
            
            
        # check that data is available
        if aveUT < self.startFof2UT or aveUT > self.endFof2UT:
            outputArr[:1] = numpy.nan
            return
        
        # check if cache needs to be updated
        updateNeeded = False
        try:
            if len(self.fof2Table) == 0:
                updateNeeded = True 
            elif (aveUT < self.fof2Table['ut1_unix'][0] or aveUT > self.fof2Table['ut1_unix'][-1]):
                updateNeeded = True
        except ValueError:
            updateNeeded = True
        if updateNeeded:
            filename = os.path.join(self.madroot, dataFile)
            f = h5py.File(filename, 'r')
            self.fof2Table = f['Data']['Table Layout']
            cond1 = numpy.where(self.fof2Table['ut1_unix'] > aveUT - self.numSecsToCache)
            cond2 = numpy.where(self.fof2Table['ut1_unix'] < aveUT + self.numSecsToCache)
            selection = numpy.intersect1d(cond1, cond2)
            self.fof2Table = numpy.array(self.fof2Table[selection.tolist()])
            f.close()
            if len(self.fof2Table) == 0:
                outputArr[:1] = numpy.nan
                return
            
        # find out where this value fits
        index = numpy.searchsorted(self.fof2Table['ut1_unix'], [aveUT])[0]
        if index == 0:
            outputArr[:1] = numpy.nan
            return
        
        correctRow = None
        if aveUT - self.fof2Table['ut1_unix'][index-1] <= 1800.0: # 30 minutes - the spacing of data in file
            correctRow = self.fof2Table[index-1]
        else:
            outputArr[:1] = numpy.nan
            return
        
        outputArr[0] = correctRow['fof2_mlh']
        
        return
    
    
    def getNeNe8(self, inputArr, outputArr):
        """getNeNe8 modifies the outputArr with the values of:
        
            NE
            
            given an inputArr with:
            
            NE8
        """
        outputArr[0] = inputArr[0];
        
        
    def getDNeDNe8(self, inputArr, outputArr):
        """getDNeDNe8 modifies the outputArr with the values of:
        
            DNE
            
            given an inputArr with:
            
            DNE8
        """
        outputArr[0] = inputArr[0];
    
    
    
    def getIri(self, inputArr, outputArr):
        """getIri modifies the outputArr with the values of:
        
            NE_IRI, NEL_IRI, TN_IRI, TI_IRI, TE_IRI,
            PO+_IRI, PNO+_IRI, PO2+_IRI, PHE+_IRI, PH+_IRI, PN+_IRI
            
            given an inputArr with:
            
            UT1_UNIX, UT2_UNIX, YEAR, MONTH, DAY, HOUR, MIN, SEC, GDLAT, GDLON, GDALT
        """
        # the first step is to create an array of 13 ap3 values (as ints), with times from 12*3 hours ago to 
        # present time
        if self.iri_iap3 is None:
            self.iri_iap3 = numpy.zeros((13,), dtype=numpy.int32)
            self.iri_f107 = None
            
        # see if we need to refresh the cache
        if self.lastUT1_Unix_iri != inputArr[0]:
            self.lastUT1_Unix_iri = inputArr[0]
            # temp arrays to pass into getGeo
            inArr = numpy.zeros((2,), dtype='f8')
            outArr = numpy.zeros((5,), dtype='f8')
            for i in range(13):
                inArr[0] = inputArr[0] - ((3*12*3600) - (i*3*3600))
                inArr[1] = inputArr[1] - ((3*12*3600) - (i*3*3600))
                self.getGeo(inArr, outArr)
                if numpy.isnan(outArr[1]):
                    self.iri_f107 = None # force future calls with same ut1 to fail
                    outputArr[:11] = numpy.nan
                    return
                self.iri_iap3[i] = int(outArr[1])
                if i == 12:
                    if numpy.isnan(outArr[3]):
                        self.iri_f107 = None # force future calls with same ut1 to fail
                        outputArr[:11] = numpy.nan
                        return
                    self.iri_f107 = outArr[3]
                    
        else:
            # use cache
            if self.iri_f107 is None:
                # bad geophysical data
                outputArr[:11] = numpy.nan
                return
                
        # get inputs
        year = int(inputArr[2])
        month = int(inputArr[3])
        day = int(inputArr[4])
        hour = int(inputArr[5])
        minute = int(inputArr[6])
        second = int(inputArr[7])
        gdlat = inputArr[8]
        glon = inputArr[9]
        gdalt = inputArr[10]
            
        madrigal._derive.madRunIri(year, month, day, hour, minute, second,
                                   gdlat, glon, gdalt, self.iri_iap3, self.iri_f107, outputArr)
        
        
        
        
        
    def getVisrNe(self, inputArr, outputArr):
        """getVisrNe modifies the outputArr with the values of:
        
            "NE_MODEL", "NEL_MODEL"
            
            given an inputArr with:
            
            "UT1_UNIX", "UT1",  "KINST", "SLT", "GDALT", "GDLAT", "ELM"
            
            This method calls self.getGeo for some earlier times because that is what
            Shunrong's model requires, then calls Shonrong's Fortran isrim method
            via madrigal._derive.isrim
        """
        ut1_unix = inputArr[0]
        ut1 = inputArr[1]
        kinst = int(inputArr[2])
        slt = inputArr[3]
        gdalt = inputArr[4]
        gdlat = inputArr[5]
        elm = inputArr[6]
        
        if not kinst in [20,25,30,31,32,40,72,80,95,5340,5360]:
            # only applies to certain sites
            outputArr[:2] = numpy.nan
            return
        
        ipar = 1 # gets Ne
        
        # check that elevation is greater than 75 if only local model 
        
        if (kinst in (72, 80, 95) and (elm < 75.0)):
            # local model does not apply
            outputArr[:2] = numpy.nan
            return
        
        # get geo data 3 hours before UT1 and 24 hours before UT1
        newInputArr = numpy.array([ut1_unix - 10800.0, ut1_unix - 10800.0], dtype='f8') # 3 hours hour before
        newOutputArr = numpy.zeros((5,), dtype='f8')
        self.getGeo(newInputArr, newOutputArr)
        ap3_3hour = newOutputArr[1]
        if numpy.isnan(ap3_3hour):
            outputArr[:2] = numpy.nan
            return
        newInputArr[:] = ut1_unix - 86400.0 # 24 hours before
        self.getGeo(newInputArr, newOutputArr)
        f107_24hour = newOutputArr[3] * 1.0E22
        if numpy.isnan(f107_24hour):
            outputArr[:2] = numpy.nan
            return

        madrigal._derive.madIsrim(ut1, kinst, slt, gdalt, gdlat,
                                  f107_24hour, ap3_3hour, ipar, outputArr)
        
        return
    
    
    
    def getVisrTe(self, inputArr, outputArr):
        """getVisrTe modifies the outputArr with the values of:
        
            "TE_MODEL"
            
            given an inputArr with:
            
            "UT1_UNIX", "UT1",  "KINST", "SLT", "GDALT", "GDLAT", "ELM"
            
            This method calls self.getGeo for some earlier times because that is what
            Shunrong's model requires, then calls Shonrong's Fortran isrim method
            via madrigal._derive.isrim
        """
        ut1_unix = inputArr[0]
        ut1 = inputArr[1]
        kinst = int(inputArr[2])
        slt = inputArr[3]
        gdalt = inputArr[4]
        gdlat = inputArr[5]
        elm = inputArr[6]
        
        if not kinst in [20,25,30,31,32,40,72,80,95,5340,5360]:
            # only applies to certain sites
            outputArr[:2] = numpy.nan
            return
        
        ipar = 2 # gets Te
        
        # check that elevation is greater than 75 if only local model 
        
        if (kinst in (72, 80, 95) and (elm < 75.0)):
            # local model does not apply
            outputArr[:2] = numpy.nan
            return
        
        # get geo data 3 hours before UT1 and 24 hours before UT1
        newInputArr = numpy.array([ut1_unix - 10800.0, ut1_unix - 10800.0], dtype='f8') # 3 hours hour before
        newOutputArr = numpy.zeros((5,), dtype='f8')
        self.getGeo(newInputArr, newOutputArr)
        ap3_3hour = newOutputArr[1]
        if numpy.isnan(ap3_3hour):
            outputArr[:2] = numpy.nan
            return
        newInputArr[:] = ut1_unix - 86400.0 # 24 hours before
        self.getGeo(newInputArr, newOutputArr)
        f107_24hour = newOutputArr[3] * 1.0E22
        if numpy.isnan(f107_24hour):
            outputArr[:2] = numpy.nan
            return
        
        madrigal._derive.madIsrim(ut1, kinst, slt, gdalt, gdlat,
                                  f107_24hour, ap3_3hour, ipar, outputArr)
        
        return
    
    
    
    def getVisrTi(self, inputArr, outputArr):
        """getVisrTi modifies the outputArr with the values of:
        
            "TI_MODEL"
            
            given an inputArr with:
            
            "UT1_UNIX", "UT1",  "KINST", "SLT", "GDALT", "GDLAT", "ELM"
            
            This method calls self.getGeo for some earlier times because that is what
            Shunrong's model requires, then calls Shonrong's Fortran isrim method
            via madrigal._derive.isrim
        """
        ut1_unix = inputArr[0]
        ut1 = inputArr[1]
        kinst = int(inputArr[2])
        slt = inputArr[3]
        gdalt = inputArr[4]
        gdlat = inputArr[5]
        elm = inputArr[6]
        
        if not kinst in [20,25,30,31,32,40,72,80,95,5340,5360]:
            # only applies to certain sites
            outputArr[:2] = numpy.nan
            return
        
        ipar = 3 # gets Ti
        
        # check that elevation is greater than 75 if only local model 
        
        if (kinst in (72, 80, 95) and (elm < 75.0)):
            # local model does not apply
            outputArr[:2] = numpy.nan
            return
        
        # get geo data 3 hours before UT1 and 24 hours before UT1
        newInputArr = numpy.array([ut1_unix - 10800.0, ut1_unix - 10800.0], dtype='f8') # 3 hours hour before
        newOutputArr = numpy.zeros((5,), dtype='f8')
        self.getGeo(newInputArr, newOutputArr)
        ap3_3hour = newOutputArr[1]
        if numpy.isnan(ap3_3hour):
            outputArr[:2] = numpy.nan
            return
        newInputArr[:] = ut1_unix - 86400.0 # 24 hours before
        self.getGeo(newInputArr, newOutputArr)
        f107_24hour = newOutputArr[3] * 1.0E22
        if numpy.isnan(f107_24hour):
            outputArr[:2] = numpy.nan
            return
        
        madrigal._derive.madIsrim(ut1, kinst, slt, gdalt, gdlat,
                                  f107_24hour, ap3_3hour, ipar, outputArr)
        
        return
    
    
    def getVisrVo(self, inputArr, outputArr):
        """getVisrVo modifies the outputArr with the values of:
        
            "VO_MODEL"
            
            given an inputArr with:
            
            "UT1_UNIX", "UT1",  "KINST", "SLT", "GDALT", "GDLAT", "ELM"
            
            This method calls self.getGeo for some earlier times because that is what
            Shunrong's model requires, then calls Shonrong's Fortran isrim method
            via madrigal._derive.isrim
        """
        ut1_unix = inputArr[0]
        ut1 = inputArr[1]
        kinst = int(inputArr[2])
        slt = inputArr[3]
        gdalt = inputArr[4]
        gdlat = inputArr[5]
        elm = inputArr[6]
        
        if not kinst in [20,30,32,80,95,5340,5360]:
            # only applies to certain sites
            outputArr[:2] = numpy.nan
            return
        
        ipar = 4 # gets Vo
        
        # check that elevation is greater than 75 if only local model 
        
        if (kinst in (80, 95) and (elm < 75.0)):
            # local model does not apply
            outputArr[:2] = numpy.nan
            return
        
        # get geo data 3 hours before UT1 and 24 hours before UT1
        newInputArr = numpy.array([ut1_unix - 10800.0, ut1_unix - 10800.0], dtype='f8') # 3 hours hour before
        newOutputArr = numpy.zeros((5,), dtype='f8')
        self.getGeo(newInputArr, newOutputArr)
        ap3_3hour = newOutputArr[1]
        if numpy.isnan(ap3_3hour):
            outputArr[:2] = numpy.nan
            return
        newInputArr[:] = ut1_unix - 86400.0 # 24 hours before
        self.getGeo(newInputArr, newOutputArr)
        f107_24hour = newOutputArr[3] * 1.0E22
        if numpy.isnan(f107_24hour):
            outputArr[:2] = numpy.nan
            return
        
        madrigal._derive.madIsrim(ut1, kinst, slt, gdalt, gdlat,
                                  f107_24hour, ap3_3hour, ipar, outputArr)
        
        return
    
    
    def getVisrHNMax(self, inputArr, outputArr):
        """getVisrHNMax modifies the outputArr with the values of:
        
            "HMAX_MODEL", "NMAX_MODEL"
            
            given an inputArr with:
            
            "UT1_UNIX", "UT1",  "KINST", "SLT", "GDALT", "GDLAT", "ELM"
            
            This method calls self.getGeo for some earlier times because that is what
            Shunrong's model requires, then calls Shonrong's Fortran isrim method
            via madrigal._derive.isrim
        """
        ut1_unix = inputArr[0]
        ut1 = inputArr[1]
        kinst = int(inputArr[2])
        slt = inputArr[3]
        gdalt = inputArr[4]
        gdlat = inputArr[5]
        elm = inputArr[6]
        
        if not kinst in [20,25,30,31,32,40,72,80,95,5340,5360]:
            # only applies to certain sites
            outputArr[:2] = numpy.nan
            return
        
        ipar = 5 # gets HMAX, NMAX
        
        # check that elevation is greater than 75 if only local model 
        
        if (kinst in (72, 80, 95) and (elm < 75.0)):
            # local model does not apply
            outputArr[:2] = numpy.nan
            return
        
        # get geo data 3 hours before UT1 and 24 hours before UT1
        newInputArr = numpy.array([ut1_unix - 10800.0, ut1_unix - 10800.0], dtype='f8') # 3 hours hour before
        newOutputArr = numpy.zeros((5,), dtype='f8')
        self.getGeo(newInputArr, newOutputArr)
        ap3_3hour = newOutputArr[1]
        if numpy.isnan(ap3_3hour):
            outputArr[:2] = numpy.nan
            return
        newInputArr[:] = ut1_unix - 86400.0 # 24 hours before
        self.getGeo(newInputArr, newOutputArr)
        f107_24hour = newOutputArr[3] * 1.0E22
        if numpy.isnan(f107_24hour):
            outputArr[:2] = numpy.nan
            return
        
        madrigal._derive.madIsrim(ut1, kinst, slt, gdalt, gdlat,
                                  f107_24hour, ap3_3hour, ipar, outputArr)
        
        return
    
    
    def getNeut(self, inputArr, outputArr):
        """getNeut modifies the outputArr with the values of:
        
          "TNM", "TINFM", "MOL", "NTOTL", "NN2L",
          "NO2L", "NOL", "NARL", "NHEL", "NHL",
          "NN4SL", "NPRESL", "PSH",
          "DTNM", "DTINFM", "DMOL", "DNTOTL", "DNN2L",
          "DNO2L", "DNOL", "DNARL", "DNHEL", "DNHL",
          "DNN4SL", "DNPRESL", "DPSH"
            
            given an inputArr with:
            
            UT1_UNIX, UT2_UNIX, YEAR, MONTH, DAY, HOUR, MIN, SEC, GDLAT, GDLON, GDALT
            
            This method calls self.getGeo for some earlier times because that is what
            MSIS requires
        """
        if self.msis_ap is None:
            self.msis_ap = numpy.zeros((7,), dtype='f8')
        
        # see if we need to refresh the cache
        if self.lastUT1_Unix_msis != inputArr[0]:
            self.lastUT1_Unix_msis = inputArr[0]
            # get previous geophysical data as specified by the MSIS model
            # temp arrays to pass into getGeo
            inArr = numpy.zeros((2,), dtype='f8')
            outArr = numpy.zeros((5,), dtype='f8')
            for i in range(20):
                inArr[0] = inputArr[0] - (i*3*3600)
                inArr[1] = inputArr[1] - (i*3*3600)
                self.getGeo(inArr, outArr)
                if numpy.isnan(outArr[2]):
                    self.msis_fbar = None
                    outputArr[:26] = numpy.nan
                    return
                
                if i == 0:
                    self.msis_ap[0] = outArr[2]
                    self.msis_ap[1] = outArr[1]
                    if numpy.isnan(outArr[4]):
                        self.msis_fbar = None
                        outputArr[:26] = numpy.nan
                        return
                    self.msis_fbar = outArr[4]*1.0e22
                    continue
                
                if i in (1,2,3):
                    self.msis_ap[i+1] = outArr[2]
                    continue
                
                if i in (4,5,6,7,8,9,10,11):
                    self.msis_ap[5] += outArr[1]/8.0;
                    if i == 8:
                        if numpy.isnan(outArr[3]):
                            self.msis_fbar = None
                            outputArr[:26] = numpy.nan
                            return
                        self.msis_f107 = outArr[3]*1.0e22
                    continue
                
                self.msis_ap[6] += outArr[1]/8.0
                
        else:
            # use cache
            if self.msis_fbar is None:
                # bad geophysical data
                outputArr[:26] = numpy.nan
                return
        
        
         # get inputs
        year = int(inputArr[2])
        month = int(inputArr[3])
        day = int(inputArr[4])
        hour = int(inputArr[5])
        minute = int(inputArr[6])
        second = int(inputArr[7])
        gdlat = inputArr[8]
        glon = inputArr[9]
        gdalt = inputArr[10]
        
        madrigal._derive.madRunMsis(year, month, day, hour, minute, second,
                                    gdlat, glon, gdalt, self.msis_ap, self.msis_fbar, 
                                    self.msis_f107, outputArr)
        return
    
    
    def getTsygan(self, inputArr, outputArr):
        """getTsygan modifies the outputArr with the values of:
        
            "TSYG_EQ_XGSM","TSYG_EQ_YGSM","TSYG_EQ_XGSE","TSYG_EQ_YGSE"
            
            given an inputArr with:
            
            UT1_UNIX, UT2_UNIX, UT1, UT2, GDLAT, GDLON, GDALT
            
            This method calls self.getImf and getDst for some earlier times because that is what
            Tsyganenko model requires
            
            self.lastUT1_Unix_tsygan = None
        self.tsygan_swspd = None
        self.tsygan_ygsm_now = None
        self.tsygan_zgsm = None
        self.tsygan_swden = None
        self.tsygan_dst = None
        """
        if self.tsygan_swspd is None:
            self.tsygan_swspd = numpy.zeros((24,), dtype='f8')
            self.tsygan_zgsm = numpy.zeros((24,), dtype='f8')
            self.tsygan_swden = numpy.zeros((24,), dtype='f8')
        
        # see if we need to refresh the cache
        if self.lastUT1_Unix_tsygan != inputArr[0]:
            self.lastUT1_Unix_tsygan = inputArr[0]
            # get previous geophysical data as specified by the Tsyganenko model
            # temp arrays to pass into getImf
            inArr = numpy.zeros((2,), dtype='f8')
            outArr = numpy.zeros((10,), dtype='f8')
            for i in range(24):
                inArr[0] = inputArr[0] - ((23-i)*3600)
                inArr[1] = inputArr[1] - ((23-i)*3600)
                self.getImf(inArr, outArr)
                if numpy.any(numpy.isnan(outArr[:10])):
                    self.tsygan_ygsm_now = None
                    outputArr[:4] = numpy.nan
                    return
                self.tsygan_swspd[i] = outArr[8]
                self.tsygan_zgsm[i] = outArr[2] * 1.0E9
                self.tsygan_swden[i] = outArr[7]
                
                if i == 23: # the present
                    self.tsygan_ygsm_now = outArr[1] * 1.0E9
                
            # finally, get present dst
            self.getDst(inArr, outArr)
            if numpy.isnan(outArr[0]):
                self.tsygan_ygsm_now = None
                outputArr[:4] = numpy.nan
                return
            self.tsygan_dst = outArr[0]
                
                
        else:
            # use cache
            if self.tsygan_ygsm_now is None:
                # bad geophysical data
                outputArr[:4] = numpy.nan
                return
        
         # get inputs
        mid_time = (inputArr[2] + inputArr[3])/2.0
        gdlat = inputArr[4]
        glon = inputArr[5]
        gdalt = inputArr[6]
        
        madrigal._derive.madRunTsygan(mid_time, gdlat, glon, gdalt, self.tsygan_swspd, 
                                      self.tsygan_ygsm_now, self.tsygan_zgsm, self.tsygan_swden,
                                      self.tsygan_dst, outputArr)
        return
    
    
    def getFirstTime(self, inputArr, outputArr):
        """getFirstTime modifies the outputArr with the values of:
        
          "FIRST_IBYR", "FIRST_IBDT", "FIRST_IBHM", "FIRST_IBCS"
            
           given an inputArr with:
            
            "UT1_UNIX", "UT2_UNIX"
            
            This method uses self.firstDT, and ignores inputs.  Raises error if self.firstDT is None
        """
        if self.firstDT is None:
            raise ValueError('getFirstTime cannot be called with self.firstTime == None')
        outputArr[0] = float(self.firstDT.year)
        outputArr[1] = float(self.firstDT.month * 100 + self.firstDT.day)
        outputArr[2] = float(self.firstDT.hour * 100 + self.firstDT.minute)
        outputArr[3] = float(self.firstDT.second * 100 + self.firstDT.microsecond/1.0E4)
        return
    
    
    def getAacgm(self, inputArr, outputArr):
        """getAacgm modifies the outputArr with the values of:
        
          "AACGM_LAT","AACGM_LONG", "MLT"
            
           given an inputArr with:
            
            "UT1_UNIX", "UT1_UNIX", "GDLAT", "GLON", "GDALT"
            
           Uses the external module aacgmv2
        """
        t = (inputArr[0] + inputArr[1])/2.0
        dt = datetime.datetime.fromtimestamp(t, datetime.UTC)
        if inputArr[4] > 2000.0:
            # beyond model
            outputArr[0:3] = numpy.nan
            return
        try:
            result = aacgmv2.convert_latlon(inputArr[2], inputArr[3], inputArr[4], dt)
        except:
            outputArr[0:3] = numpy.nan
            return
        outputArr[0] = result[0]
        outputArr[1] = result[1]
        # mlt
        try:
            result2 = aacgmv2.convert_mlt(result[1], dt)
        except:
            outputArr[2] = numpy.nan
            return
        outputArr[2] = result2[0]
        
        
        
    def fromAacgm(self, inputArr, outputArr):
        """getAacgm modifies the outputArr with the values of:
        
          "GDLAT", "GLON"
            
           given an inputArr with:
            
            "UT1_UNIX", "UT2_UNIX", "AACGM_LAT","AACGM_LONG","GDALT"
            
           Uses the external module aacgmv2
           
        """
        t = (inputArr[0] + inputArr[1])/2.0
        dt = datetime.datetime.fromtimestamp(t, datetime.UTC)
        try:
            result = aacgmv2.convert([inputArr[2]], [inputArr[3]], [inputArr[4]], dt)
        except:
            outputArr[0:2] = numpy.nan
            return
        outputArr[0] = result[0][0]
        outputArr[1] = result[1][0]
        
        
    
    
    def traceMagneticField(self, year, month, day, hour, minute, second, 
                           inputType, outputType, in1, in2, in3,
                           model, qualifier, stopAlt, resultArr):
        """traceMagneticField returns the termination point of a magnetic field line trace.  Depending on
        model input, uses either Tsyganenko of IGRF model
        
         Unlike other methods in this class, is not meant to be called via dispatchPython. It is simply
         a helper method.
         
         Inputs:
             1-6. year, month, day, hour, minute, second as ints
             7. inputType (0 for geodetic, 1 for GSM)
             8. outputType (0 for geodetic, 1 for GSM)
               (the following parameters depend on inputType)
             9. in1 - geodetic altitude or ZGSM of starting point
             10. in2 - geodetic latitude or XGSM of starting point
             11. in3 - longitude or YGSM of starting point
             12. model - 0 for Tsygenanko, 1 for IGRF
             13. int qualifier - 0 for conjugate, 1 for north_alt, 2 for south_alt, 3 for apex
                4 for GSM XY plane - but not possible for IGRF, so raises an error
             14. Python double stopAlt - altitude to stop trace at, if qualifier is north_alt or south_alt.
                If other qualifier, this parameter is ignored
             15. Python double 1D numpy vector representing the 3 outputs, whose meaning depends on outputType
                    end_1 - geodetic altitude or ZGSM of starting point
                    end_2 - geodetic latitude or XGSM of starting point
                    end_3 - longitude or YGSM of starting point

            
         Returns: 0 to indicate result calculated (which still may be nan)
            
        Calls either madrigal._derive.traceTsygenankoField or madrigal._derive.traceIGRFField
        """
        if model not in (0, 1):
            raise ValueError("Model must be 0 for Tsyganenko, or 1 for IGRF, not %s" % (str(model)))
        
        if model == 0:
            # Tsygenenko requires previous geophysical data 
            dt = datetime.datetime(year, month, day, hour, minute, second)
            unix_time = calendar.timegm(dt.utctimetuple())
            # get previous geophysical data as specified by the Tsyganenko model
            # temp arrays to pass into getImf
            tsygan_swspd = numpy.zeros((24,), dtype='f8')
            tsygan_zgsm = numpy.zeros((24,), dtype='f8')
            tsygan_swden = numpy.zeros((24,), dtype='f8')
            inArr = numpy.zeros((2,), dtype='f8')
            outArr = numpy.zeros((10,), dtype='f8')
            for i in range(24):
                inArr[0] = unix_time - ((23-i)*3600)
                inArr[1] = unix_time - ((23-i)*3600)
                self.getImf(inArr, outArr)
                if numpy.any(numpy.isnan(outArr[:10])):
                    resultArr[:3] = numpy.nan
                    return
                tsygan_swspd[i] = outArr[8]
                tsygan_zgsm[i] = outArr[2] * 1.0E9
                tsygan_swden[i] = outArr[7]
                
                if i == 23: # the present
                    tsygan_ygsm_now = outArr[1] * 1.0E9
                
            # finally, get present dst
            self.getDst(inArr, outArr)
            if numpy.isnan(outArr[0]):
                resultArr[:3] = numpy.nan
                return
            tsygan_dst = outArr[0]
            
            madrigal._derive.traceTsyganenkoField(year, month, day, hour, minute, second,
                                                  inputType, outputType, in1, in2, in3,
                                                  tsygan_swspd, tsygan_ygsm_now, tsygan_zgsm,
                                                  tsygan_swden, tsygan_dst, qualifier, stopAlt,
                                                  resultArr)
            
        else:
            # IGRF
            madrigal._derive.traceIGRFField(year, inputType, outputType, in1, in2, in3,
                                            qualifier, stopAlt, resultArr)
            
    
    
    def getFaradayRotation(self, year, month, day, hour, minute, second, 
                           sgdlat, slon, sgdalt, gdlat, glon, gdalt, freq):
        """getFaradayRotation returns (one way faraday rotation, total tec along line, total tec out to 22000 km)
        
         Unlike other methods in this class, is not meant to be called via dispatchPython. It is simply
         a helper method.
         
         Inputs:
             1. year, month, day, hour, minute, second as ints
             2. observer location as sgdlat, slon, sgdalt
             3. starting location as gdlat, glon, gdalt
             5. freq in Hz
            
         Returns: a tuple with three items:
            1. one way faraday rotation in radians, NAN if error
            2. total tec from station to point in electrons/m^2
            3. total tec from station to 22000 km along line through point in electrons/m^2
            
            If error, returns a tuple of (None, None, None)
            
        Calls madrigal._derive.faradayRotation
        """
        # get geophysica data
        iri_iap3 = numpy.zeros((13,), dtype=numpy.int32)
        # temp arrays to pass into getGeo
        inArr = numpy.zeros((2,), dtype='f8')
        outArr = numpy.zeros((5,), dtype='f8')
        dt = datetime.datetime(year, month, day, hour, minute, second)
        unix_time = calendar.timegm(dt.utctimetuple())
        for i in range(13):
            inArr[0] = unix_time - ((3*12*3600) - (i*3*3600))
            inArr[1] = unix_time - ((3*12*3600) - (i*3*3600))
            self.getGeo(inArr, outArr)
            if numpy.isnan(outArr[1]):
                return((None,None,None))
            iri_iap3[i] = int(outArr[1])
            if i == 12:
                if numpy.isnan(outArr[3]):
                    return((None,None,None))
                iri_f107 = outArr[3]
                
        return(madrigal._derive.faradayRotation(year, month, day, hour, minute, second, 
                                                sgdlat, slon, sgdalt, gdlat, glon, gdalt, freq,
                                                iri_iap3, iri_f107))
        
    def getB_up(self, inputArr, outputArr):
        """getB_up modifies the outputArr with the values of:
        
          "B_UP"
            
           given an inputArr with:
            
            "BD"
            
            Simply set B_UP to -1*BD
        """
        outputArr[0] = -1.0 * inputArr[0]
        return
    
    
    def getBd(self, inputArr, outputArr):
        """getBd modifies the outputArr with the values of:
        
          "BD"
            
           given an inputArr with:
            
            "B_UP"
            
            Simply set BD to -1*B_UP
        """
        outputArr[0] = -1.0 * inputArr[0]
        return
    
    
    def getDiff_B_up(self, inputArr, outputArr):
        """getDiff_B_up modifies the outputArr with the values of:
        
          "DIFF_B_UP"
            
           given an inputArr with:
            
            "DIFF_BD"
            
            Simply set DIFF_B_UP to -1*DIFF_BD
        """
        outputArr[0] = -1.0 * inputArr[0]
        return
    
    
    def getDiff_Bd(self, inputArr, outputArr):
        """getDiff_Bd modifies the outputArr with the values of:
        
          "DIFF_BD"
            
           given an inputArr with:
            
            "DIFF_B_UP"
            
            Simply set DIFF_BD to -1*DIFF_B_UP
        """
        outputArr[0] = -1.0 * inputArr[0]
        return
    

    def getGeod(self, inputArr, outputArr):
        """getGeod derives Geodetic lat, long and alt from kinst, azm, elm, and range
        
        getGeod modifies the outputArr with the values of:

           "GDLAT", "GLON", "GDALT":
                  GDLAT - geodetic latitude of measurement
                  GLON - geodetic longitude of measurement
                  GDALT - geodetic altitude of measurement (km)

        given an inputArr with:

           "KINST", "AZM", "ELM", "RANGE":
                  KINST - instrument id
                  AZM - mean azimuth in deg
                  ELM - mean elevation in deg
                  RANGE - range in km
        """
        kinst = int(inputArr[0])
        azm = inputArr[1]
        elm = inputArr[2]
        range = inputArr[3]
        
        instAlt = self.madInst.getAltitude(kinst)
        instLat = self.madInst.getLatitude(kinst)
        instLon = self.madInst.getLongitude(kinst)

        # aer2geodetic takes range and instAlt in meters, outAlt in meters
        outLat, outLon, outAlt = pymap3d.aer.aer2geodetic(azm, elm, range * 1000, instLat, instLon, instAlt * 1000)
        outputArr[0] = outLat
        outputArr[1] = outLon
        outputArr[2] = outAlt / 1000.0
        return
    

    def getDGeod(self, inputArr, outputArr):
        """getDGeod derives error in Geodetic lat, long and alt
             from azm, dazm, elm, delm, range, and drange
        
        getDGeod modifies the outputArr with the values of:

           "DGDLAT", "DGLON", "DGDALT":
                  DGDLAT - error in geodetic latitude
                  DGLON - error in geodetic longitude
                  DGDALT - error in geodetic altitude

           given an inputArr with:

           "KINST", "AZM", "DAZM", "ELM", "DELM", "RANGE", "DRANGE":
                  KINST - instrument id
                  AZM - mean azimuth in deg
                  DAZM - error in mean azimuth
                  ELM - mean elevation in deg
                  DELM - error in mean elevation
                  RANGE - range in km
                  DRANGE - error in range

        Algorithm: Calculate derivatives with respect to AZM, ELM, and
               RANGE by simply finding the difference with them
               incremented by 1 degree or 1 km.  These derivitives
               are:
                  dlatdaz, dlatdel, dlatdrange
                  dlondaz, dlondel, dlondrange
                  daltdaz, daltdel, daltdrange
 
               then:
 
        dgdlat = ((dlatdaz*dazm)^2 + (dlatdel*delm)^2 + (dlatdrange*drange)^2)^1/2
        dgdlon = ((dlondaz*dazm)^2 + (dlondel*delm)^2 + (dlondrange*drange)^2)^1/2
        dgdalt = ((daltdaz*dazm)^2 + (daltdel*delm)^2 + (daltdrange*drange)^2)^1/2
        """
        # aer2geodetic takes range and instAlt in meters, outAlt in meters
        kinst = int(inputArr[0])
        azm = inputArr[1]
        dazm = inputArr[2]
        elm = inputArr[3]
        delm = inputArr[4]
        range = inputArr[5] * 1000
        drange = inputArr[6]
        
        instAlt = self.madInst.getAltitude(kinst) * 1000
        instLat = self.madInst.getLatitude(kinst)
        instLon = self.madInst.getLongitude(kinst)

        dlatdaz = None
        dlatdel = None
        dlatdrange = None
        dlondaz = None
        dlondel = None
        dlondrange = None
        daltdaz = None
        daltdel = None
        daltdrange = None

        sLat, sLon, sAlt = pymap3d.aer.aer2geodetic(azm, elm, range, instLat, instLon, instAlt)
        eLat, eLon, eAlt = pymap3d.aer.aer2geodetic(azm+1, elm, range, instLat, instLon, instAlt)
        dlatdaz = eLat - sLat
        eLat, eLon, eAlt = pymap3d.aer.aer2geodetic(azm, elm+1, range, instLat, instLon, instAlt)
        dlatdel = eLat - sLat
        eLat, eLon, eAlt = pymap3d.aer.aer2geodetic(azm, elm, range+1000, instLat, instLon, instAlt)
        dlatdrange = eLat - sLat
        eLat, eLon, eAlt = pymap3d.aer.aer2geodetic(azm+1, elm, range, instLat, instLon, instAlt)
        dlondaz = eLon - sLon
        eLat, eLon, eAlt = pymap3d.aer.aer2geodetic(azm, elm+1, range, instLat, instLon, instAlt)
        dlondel = eLon - sLon
        eLat, eLon, eAlt = pymap3d.aer.aer2geodetic(azm, elm, range+1000, instLat, instLon, instAlt)
        dlondrange = eLon - sLon
        eLat, eLon, eAlt = pymap3d.aer.aer2geodetic(azm+1, elm, range, instLat, instLon, instAlt)
        daltdaz = eAlt - sAlt
        eLat, eLon, eAlt = pymap3d.aer.aer2geodetic(azm, elm+1, range, instLat, instLon, instAlt)
        daltdel = eAlt - sAlt
        eLat, eLon, eAlt = pymap3d.aer.aer2geodetic(azm, elm, range+1000, instLat, instLon, instAlt)
        daltdrange = eAlt - sAlt

        dgdlat = math.sqrt(((dlatdaz * dazm) ** 2) + ((dlatdel * delm) ** 2) + ((dlatdrange * drange) ** 2))
        dgdlon = math.sqrt(((dlondaz * dazm) ** 2) + ((dlondel * delm) ** 2) + ((dlondrange * drange) ** 2))
        dgdalt = math.sqrt(((daltdaz * dazm) ** 2) + ((daltdel * delm) ** 2) + ((daltdrange * drange) ** 2))

        outputArr[0] = dgdlat
        outputArr[1] = dgdlon
        outputArr[2] = dgdalt / 1000.0
        return
    

    def getGeodGdalt(self, inputArr, outputArr):
        """getGeodGdalt derives Geodetic lat, long and alt from kinst, azm, elm, and gdalt
        
        getGeodGdalt modifies the outputArr with the values of:

           "GDLAT", "GLON":
                  GDLAT - geodetic latitude of measurement
                  GLON - geodetic longitude of measurement

           given an inputArr with:

           "KINST", "AZM", "ELM", "GDALT":
                  KINST - instrument id
                  AZM - mean azimuth in deg
                  ELM - mean elevation in deg
                  GDALT - alt in km
        """
        kinst = int(inputArr[0])
        azm = inputArr[1]
        elm = inputArr[2]
        range = inputArr[3]

        # protect against elm < 0.0001 deg
        if ((elm < 0.0001) or (elm > 90.0001)):
            outputArr[0] = numpy.nan
            outputArr[1] = numpy.nan
            return
        # range passed in as gdalt, convert
        range = (range / math.sin(elm / 57.29578)) * 1000

        instLat = self.madInst.getLatitude(kinst)
        instLon = self.madInst.getLongitude(kinst)
        instAlt = self.madInst.getAltitude(kinst) * 1000

        # aer2geodetic takes range and instAlt in meters, outAlt in meters
        outLat, outLon, outAlt = pymap3d.aer.aer2geodetic(azm, elm, range, instLat, instLon, instAlt)

        # force glon to between -180 and 180 
        while (outLon < -180.0):
            outLon += 360.0
        while (outLon > +180.0):
            outLon -= 360.0
        
        outputArr[0] = outLat
        outputArr[1] = outLon
        return
    

    def getGeodAlt(self, inputArr, outputArr):
        """getGeodAlt derives Geodetic lat, long by assuming measured point is
               directly above instrument
        
        getGeodAlt modifies the outputArr with the values of:

           "GDLAT", "GLON":
                  GDLAT - geodetic latitude of measurement
                  GLON - longitude of measurement

           given an inputArr with:

           "GDLATR", "GDLONR"
                  GDLATR - Inst geod latitude (N hemi=pos) - deg
                  GDLONR - Inst geod longitute - deg

        Algorithm: Sets GDLAT, GLON to station values
        """
        outputArr[0] = inputArr[0]
        outputArr[1] = inputArr[1]

        # force outputArr[1] to between -180 and 180
        while (outputArr[1] < -180.0):
            outputArr[1] += 360.0
        while (outputArr[1] > +180.0):
            outputArr[1] -= 360.0
        return
    

    def getAzElRange(self, inputArr, outputArr):
        """getAzElRange derives Azm, Elm, and Range given gdlat, glon, gdalt
        (point position) and gdlatr, glonr, galtr (station position)
        
        getAlElRange modifies the outputArr with the values of:

           "AZM", "ELM", "RANGE":
                  AZM - mean azimuth in deg
                  ELM - mean elevation in deg
                  RANGE - range in km

            given an inputArr with:

            "GDLAT", "GLON", "GDALT", "GDLATR", "GDLONR", "GALTR":
                  GDLAT - geodetic latitude of measurement
                  GLON - longitude of measurement
                  GDALT - geodetic altitude of measurement in km
                  GDLATR - Inst geod latitude (N hemi=pos) - deg
                  GDLONR - Inst geod longitute - deg
                  GALTR - geodetic altitude of station in km
        """
        gdlat  = inputArr[0]
        glon   = inputArr[1]
        gdalt  = inputArr[2] * 1000
        gdlatr = inputArr[3]
        gdlonr = inputArr[4]
        galtr  = inputArr[5] * 1000

        # geodetic2aer takes target and observer alt in meters, outRange in meters
        outAz, outEl, outRange = pymap3d.aer.geodetic2aer(gdlat, glon, gdalt, gdlatr, gdlonr, galtr)

        outputArr[0] = outAz
        outputArr[1] = outEl
        outputArr[2] = outRange / 1000.0
        return
        
        
    