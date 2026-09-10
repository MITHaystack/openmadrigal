"""testDerivationEngine.py creates a text output file for a set list of derivable parameters
for a set test file from a given madrigal url.

Used to regression test derivation engine

$Id: testDerivationEngine.py 7611 2023-09-18 17:25:01Z brideout $
"""

# standard python imports
import os, os.path, sys
import subprocess

# third party imports
import h5py
import numpy

# Madrigal imports
import madrigal.metadata
import madrigal.data
import madrigal.derivation

def compareColumns(tdata, rdata, mnem):
    """compareColumns compares a column of test data to rock data for mnemonic mnem
    
    Returns True is a match within numerical error within 0.1 percent.  Prints error and returns
    False if not.
    """
    if len(tdata) != len(rdata):
        print(('for mnem %s len of test data is %i but len of rock data is %i' % (mnem, len(tdata), len(rdata))))
        
    for i in range(len(tdata)):
        tpoint = tdata[i]
        rpoint = rdata[i]
        if numpy.isnan(tpoint) and numpy.isnan(rpoint):
            # match
            continue
        if numpy.isnan(tpoint) or numpy.isnan(rpoint):
            # mismatch
            print(('Failure at row %i for mnem %s - only one nan' % (i, mnem)))
            return(False)
        if float(tpoint) == 0.0 and float(rpoint) == 0.0:
            # match 
            continue
        if float(tpoint) == 0.0 or float(rpoint) == 0.0:
            # mismatch
            print(('Failure at row %i for mnem %s - only one 0.0' % (i, mnem)))
            return(False) 
        if abs(tpoint-rpoint) / abs(tpoint) > 0.001:
            print(('Failure at row %i for mnem %s - t %g, r %g' % (i, mnem, tpoint, rpoint)))
            return(False)
        
    return(True)
        
        



def compare(test, rock):
    """compare returns True if two hdf5 files equivalent, prints errors and returns False is not
    
    Inputs:
        test - newly created test hdf5 file
        rock - manually verified hdf5 file
    """
    with h5py.File(test, 'r') as ft:
        with h5py.File(rock, 'r') as fr:
            tdata = ft['Data']['Table Layout']
            rdata = fr['Data']['Table Layout']
            for mnem in tdata.dtype.names:
                if not compareColumns(tdata[mnem], rdata[mnem], mnem):
                    return(False)
                
    return(True)
            

usage = "python testDerivationEngine.py"
output = 'testDerivationEngine.h5'
rock = 'testDerivationEngine.rock.h5'
output = os.path.join(os.getcwd(), output)
if os.access(output, os.R_OK):
    os.remove(output)

# a list of parmes that have been verified
expectedDerivParms = ['IBYR', 'IBDT', 'IBHM', 'IBCS', 'IEYR', 'IEDT', 'IEHM', 'IECS', 'UT1_UNIX', 'UT2_UNIX', 
                      'KINDAT', 'KINST', 'RECNO', 'PL', 'MDTYP', 'AZ1', 'AZ2', 'EL1', 'EL2', 'SYSTMP', 'PNRMD', 
                      'POWER', 'TFREQ', 'MODE', 'PULF', 'FPI_DATAQUAL', 'DPM', 'MRESL', 'GLON', 'RANGE', 'SN', 
                      'CHISQ', 'GFIT', 'TI', 'DTI', 'TR', 'DTR', 'POPL', 'DPOPL', 'PH+', 'DPH+', 'FA', 'DFA', 
                      'PM', 'VO', 'DVO', 'VDOPP', 'DVDOPP', 'GDLAT', 'GDALT', 'NE', 'DNE', 'RANGE', 'FIRST_IBYR', 
                      'FIRST_IBDT', 'FIRST_IBHM', 'FIRST_IBCS', 'BYEAR', 'YEAR', 'MONTH', 'DAY', 'HOUR', 'MIN', 
                      'SEC', 'CSEC', 'BMD', 'BMONTH', 'BDAY', 'MD', 'DAYNO', 'BHM', 'BHHMMSS', 'EHHMMSS', 'HM', 
                      'UTH', 'UTS', 'B_UTH', 'INTTMS', 'INTTMM', 'DATNTD', 'UT', 'BEG_UT', 'JDAYNO', 
                      'JULIAN_DATE', 'JULIAN_DAY', 'UT1', 'UT2', 'DUT21', 'FYEAR', 'GDLATR', 'GDLONR', 'GALTR', 
                      'RESL', 'AZM', 'DAZ', 'ELM', 'DEL', 'SZEN', 'SLTMUT', 'SLT', 'SDWHT', 'SUNRISE', 'SUNSET', 
                      'SUNRISE_HOUR', 'SUNSET_HOUR', 'GCDIST', 'BN', 'BE', 'BD', 'BMAG', 'BDEC', 'BINC', 'LSHELL', 
                      'DIPLAT', 'INVLAT', 'APLAT', 'APLON', 'MAGCONJLAT', 'MAGCONJLON', 'CXR', 'CYR', 'CZR', 
                      'SLTC', 'APLT', 'SZENC', 'CONJ_SUNRISE', 'CONJ_SUNSET', 
                      'CONJ_SUNRISE_H', 'CONJ_SUNSET_H', 'MAGCONJSDWHT', 'TSYG_EQ_XGSM', 'TSYG_EQ_YGSM', 
                      'TSYG_EQ_XGSE', 'TSYG_EQ_YGSE', 'AACGM_LAT', 'AACGM_LONG', 'MLT', 'E_REG_S_LAT', 
                      'E_REG_S_LON', 'E_REG_S_SDWHT', 'E_REG_N_LAT', 'E_REG_N_LON', 'E_REG_N_SDWHT', 
                      'ASPECT', 'KP', 'AP3', 'AP', 'F10.7', 'FBAR', 'DST', 'FOF2_MLH', 'POP', 'NEL', 'DNEL', 
                      'TE', 'DTE', 'NE_MODEL', 'NEL_MODEL', 'TE_MODEL', 'TI_MODEL', 'VO_MODEL', 'HMAX_MODEL', 
                      'NMAX_MODEL', 'NE_MODELDIFF', 'NEL_MODELDIFF', 'TE_MODELDIFF', 'TI_MODELDIFF', 
                      'VO_MODELDIFF', 'SNP3', 'CHIP3', 'WCHSQ', 'TNM', 'MOL','NN2L', 'NO2L', 
                      'NOL', 'NARL', 'NHEL', 'NHL', 'NN4SL', 'TN',
                      'NE_IRI', 'NEL_IRI', 'TN_IRI', 'TI_IRI', 'TE_IRI', 'PO+_IRI', 'PNO+_IRI', 'PO2+_IRI', 
                      'PHE+_IRI', 'PH+_IRI', 'PN+_IRI', 'PDCON', 'PDCONL', 'HLCON', 'HLCONL',
                      'BXGSM', 'BYGSM', 'BZGSM', 'BIMF', 'BXGSE', 'BYGSE', 'BZGSE', 'SWDEN', 
                      'SWSPD', 'SWQ',]
    
madDB = madrigal.metadata.MadrigalDB()
testFile = os.path.join(madDB.getMadroot(), 'experiments/1998/mlh/20jan98/mlh980120g.002.hdf5')
madFileObj = madrigal.data.MadrigalFile(testFile, madDB)
measList = madFileObj.getMeasuredParmList()
madParmObj = madrigal.data.MadrigalParameters(madDB)
measParms = [madParmObj.getParmMnemonic(parm) for parm in measList]
derivParms = madrigal.derivation.getDerivableParms(measParms, kinst=30)
s1 = set(expectedDerivParms)
s2 = set(derivParms)
if len(s1.symmetric_difference(s2)) > 0:
    raise ValueError('Derived parm list has changed due to items %s this regression test needs to be manually reset' % (str(s1.symmetric_difference(s2))))
cmd = '%s/bin/isprint file=%s ' % (madDB.getMadroot(), testFile)
filters = 'filter=recno,3,4 '
cmd += filters
delimiter = ' '
parms = delimiter.join(derivParms)
cmd += parms + ' '
cmd += 'output=%s ' % (output)
# print(cmd)
subprocess.check_call(cmd.split())
if compare(output, rock):
    print('Success')
    os.remove(output)
else:
    print('Failure - see errors above')




    