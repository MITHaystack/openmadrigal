"""testAdminScripts.py in a regression test that will test the following scripts that
perform administrative tasks:

    createExpWithFile.py
    createRTExp.py
    changeExpStatus.py
    addFileToExp.py
    updateFileInExp.py
    changeFileStatus.py
    removeFileFromExp.py

This script assumes to standard test experiments have been installed.  Also assumes
MADROOT/experiments2 exists

Aborts if any errors found.

$Id: testAdminScripts.py 7048 2019-10-07 20:02:55Z brideout $
"""

import os, os.path, sys
import shutil
import traceback

import madrigal.metadata
import madrigal.ui.userData

print('The following is a regression test of the Madrigal admin scripts.\n')
print('For this first pass, user is registered for this experiment, but not the instrument')

# email address to send notifications to - change to your email if needed
email = 'brideout@mit.edu'


try:
    # if anything goes wrong, clean up anyway

    madDBObj = madrigal.metadata.MadrigalDB()
    madroot = madDBObj.getMadroot()
    
    madUserObj = madrigal.ui.userData.MadrigalUserData(madDBObj)
    # verify user registered with main test experiment
    usersReg = madUserObj.getRegisteredUsers('experiments/1998/mlh/20jan98')
    if email not in usersReg:
        madUserObj.registerExperiment(email, 'experiments/1998/mlh/20jan98')
    usersReg = madUserObj.getRegisteredInstUsers(30)
    if email in usersReg:
        madUserObj.unregisterInstrument(email, 30)
        
    print(('Notification emails about changing experiments should be send to <%s>' % (email)))

    expBase = os.path.join(madroot, 'experiments')
    expBase2 = os.path.join(madroot, 'experiments2')
    binDir = os.path.join(madroot, 'bin')
    
    # make sure experiments2 exists
    if not os.access(expBase2, os.R_OK):
        raise IOError('create directory madroot/experiments2 before running this test.')

    #### test of createExpWithFile.py ####
    print('Testing createExpWithFile.py ...')

    # get test file
    testFile = os.path.join(expBase, '1998/mlh/20jan98/mlh980120g.002.hdf5')
    shutil.copy(testFile, '/tmp')
    cmd = os.path.join(binDir, 'createExpWithFile.py')
    cmd += ' --madFilename=/tmp/mlh980120g.002.hdf5 '
    cmd += ' --expTitle="Bill Rideout test experiment" '
    cmd += ' --permission=0 '
    cmd += ' --fileDesc="This is just a test" '
    cmd += ' --instCode=30 '
    cmd += ' --kindat=3408 '
    cmd += ' --dirName=BillsTestExp20jan98 '
    cmd += ' --experimentsDirNum=2 '
    cmd += ' --PI="Bill Rideout" '
    cmd += ' --PIEmail="brideout@mit.edu" '
    cmd += ' --fileAnalyst="John Doe" '
    cmd += ' --fileAnalystEmail=jdoe@haystack.mit.edu '
    cmd += ' --createCachedText '
    cmd += ' --createCachedNetCDF4 '
    
    
    print('Command to be tested: <%s>' % (cmd))
    result = os.system(cmd)
    if result == 0:
        print('Test of createExpWithFile.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')

    #### test of createRTExp.py ####
    print('Testing createRTExp.py ...')
    cmd = os.path.join(binDir, 'createRTExp.py')
    cmd += ' --startDate=1998-01-20 '
    cmd += ' --inst=30 '
    cmd += ' --expTitle="Bill Rideout World Day test RT experiment" '
    cmd += ' --rtFiles=bill1.h5,bill2.hdf5 '
    cmd += ' --kindats=3408,3410 '
    cmd += ' --fileDescs="Description 1,Description 2" '
    cmd += ' --startTime=08:00:00 '
    cmd += ' --numDays=3 '
    cmd += ' --dirName=BillsRTTestExp20jan98 '
    cmd += ' --experimentsDirNum=2 '
    cmd += ' --PI="Bill Rideout" '
    cmd += ' --PIEmail="brideout@mit.edu" '
    cmd += ' --fileAnalyst="John Doe,Tom Sawyer" '
    cmd += ' --fileAnalystEmail=jdoe@haystack.mit.edu,tsawyer@haystack.mit.edu '
    
    print('Command to be tested: <%s>' % (cmd))
    result = os.system(cmd)
    if result == 0:
        print('Test of createRTExp.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')

    #### test of changeExpStatus.py ####
    print('Testing changeExpStatus.py ...')
    cmd = os.path.join(binDir, 'changeExpStatus.py')
    expDir = os.path.join(expBase2, '1998/mlh', 'BillsTestExp20jan98')
    expBaseDir = os.path.join('experiments2', '1998/mlh', 'BillsTestExp20jan98')
    cmd += ' --expDir=%s ' % (expDir)
    cmd += ' --expName="Bill Rideout World Day modified test experiment" '
    cmd += ' --siteID=%i ' % (madDBObj.getSiteID())
    cmd += ' --startDate=1998-01-20 '
    cmd += ' --startTime=12:00:00 '
    cmd += ' --endDate=1998-01-21 '
    cmd += ' --endTime=12:00:00 '
    cmd += ' --inst=31 '
    cmd += ' --security=1 '
    cmd += ' --PI="Bill Rideout" '
    cmd += ' --PIEmail="brideout@mit.edu" '
    print('Command to be tested: <%s>' % (cmd))
    result = os.system(cmd)
    if result == 0:
        print('Test of changeExpStatus.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')
    
    
    ### register with this experiment ###
    madUserObj.registerExperiment(email, expBaseDir)


    #### test of addFileToExp.py ####
    print('Testing addFileToExp.py ...')
    shutil.copy('/tmp/mlh980120g.002.hdf5', '/tmp/mlh980120g.003.hdf5')
    cmd = os.path.join(binDir, 'addFileToExp.py')
    cmd += ' --madFilename=/tmp/mlh980120g.003.hdf5 '
    cmd += ' --expDir=%s ' % (expDir)
    cmd += ' --permission=0 '
    cmd += ' --fileDesc="Another test" '
    cmd += ' --category=2 '
    cmd += ' --kindat=3408 '
    cmd += ' --fileAnalyst="Bill Rideout" '
    cmd += ' --fileAnalystEmail=brideout@mit.edu '
    cmd += ' --createCachedText '
    cmd += ' --createCachedNetCDF4 '
    print('Command to be tested: <%s>' % (cmd))
    result = os.system(cmd)
    if result == 0:
        print('Test of addFileToExp.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')


    #### test of updateFileInExp.py ####
    print('Testing updateFileInExp.py ...')
    cmd = os.path.join(binDir, 'updateFileInExp.py')
    cmd += ' --madFilename=/tmp/mlh980120g.003.hdf5 '
    cmd += ' --expDir=%s ' % (expDir)
    print('Command to be tested: <%s>' % (cmd))
    result = os.system(cmd)
    if result == 0:
        print('Test of updateFileInExp.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')

    #### test of changeFileStatus.py ####
    print('Testing changeFileStatus.py ...')
    cmd = os.path.join(binDir, 'changeFileStatus.py')
    cmd += ' --filename=mlh980120g.003.hdf5 '
    cmd += ' --expDir=%s ' % (expDir)
    cmd += ' --permission=1 '
    cmd += ' --fileDesc="Yet another file description" '
    cmd += ' --category=3 '
    cmd += ' --fileAnalyst="John Doe" '
    cmd += ' --fileAnalystEmail=jdoe@haystack.mit.edu '
    result = os.system(cmd)
    if result == 0:
        print('Test of changeFileStatus.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')

    #### test of removeFileFromExp.py ####
    print('Testing removeFileFromExp.py ...')
    cmd = os.path.join(binDir, 'removeFileFromExp.py')
    cmd += ' --filename=mlh980120g.003.hdf5 '
    cmd += ' --expDir=%s ' % (expDir)
    result = os.system(cmd)
    if result == 0:
        print('Test of removeFileFromExp.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')
    

except ValueError:
    print('FAILURE')
except:
    traceback.print_exc()
    print('FAILURE')


### final clean up ###
try:
    thisExp = os.path.join(expBase, '1998/mlh', 'BillsTestExp20jan98')
    os.system('rm -rf %s' % (thisExp))
    thisExp = os.path.join(expBase, '1998/mlh', 'BillsRTTestExp20jan98')
    os.system('rm -rf %s' % (thisExp))
    thisExp = os.path.join(expBase2, '1998/mlh', 'BillsTestExp20jan98')
    os.system('rm -rf %s' % (thisExp))
    thisExp = os.path.join(expBase2, '1998/mlh', 'BillsRTTestExp20jan98')
    os.system('rm -rf %s' % (thisExp))
    os.system('rm /tmp/mlh98*')
    madUserObj.unregisterExperiment(email, expBaseDir)
except:
    pass

print('For this second pass, user is registered for this instrument, but not the experiment')

try:
    # if anything goes wrong, clean up anyway

    madDBObj = madrigal.metadata.MadrigalDB()
    madroot = madDBObj.getMadroot()
    
    madUserObj = madrigal.ui.userData.MadrigalUserData(madDBObj)
    # verify user registered with main test experiment
    usersReg = madUserObj.getRegisteredUsers('experiments/1998/mlh/20jan98')
    if email in usersReg:
        madUserObj.unregisterExperiment(email, 'experiments/1998/mlh/20jan98')
    usersReg = madUserObj.getRegisteredInstUsers(30)
    if email not in usersReg:
        madUserObj.registerInstrument(email, 30)
        
    print(('Notification emails about this instrument should be send to <%s>' % (email)))

    expBase = os.path.join(madroot, 'experiments')
    expBase2 = os.path.join(madroot, 'experiments2')
    binDir = os.path.join(madroot, 'bin')
    
    # make sure experiments2 exists
    if not os.access(expBase2, os.R_OK):
        raise IOError('create directory madroot/experiments2 before running this test.')

    #### test of createExpWithFile.py ####
    print('Testing createExpWithFile.py ...')

    # get test file
    testFile = os.path.join(expBase, '1998/mlh/20jan98/mlh980120g.002.hdf5')
    shutil.copy(testFile, '/tmp')
    cmd = os.path.join(binDir, 'createExpWithFile.py')
    cmd += ' --madFilename=/tmp/mlh980120g.002.hdf5 '
    cmd += ' --expTitle="Bill Rideout test experiment" '
    cmd += ' --permission=0 '
    cmd += ' --fileDesc="This is just a test" '
    cmd += ' --instCode=30 '
    cmd += ' --kindat=3408 '
    cmd += ' --dirName=BillsTestExp20jan98 '
    cmd += ' --experimentsDirNum=2 '
    cmd += ' --PI="Bill Rideout" '
    cmd += ' --PIEmail="brideout@mit.edu" '
    cmd += ' --fileAnalyst="John Doe" '
    cmd += ' --fileAnalystEmail=jdoe@haystack.mit.edu '
    cmd += ' --createCachedText '
    cmd += ' --createCachedNetCDF4 '
    
    
    print('Command to be tested: <%s>' % (cmd))
    result = os.system(cmd)
    if result == 0:
        print('Test of createExpWithFile.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')

    #### test of createRTExp.py ####
    print('Testing createRTExp.py ...')
    cmd = os.path.join(binDir, 'createRTExp.py')
    cmd += ' --startDate=1998-01-20 '
    cmd += ' --inst=30 '
    cmd += ' --expTitle="Bill Rideout World Day test RT experiment" '
    cmd += ' --rtFiles=bill1.h5,bill2.hdf5 '
    cmd += ' --kindats=3408,3410 '
    cmd += ' --fileDescs="Description 1,Description 2" '
    cmd += ' --startTime=08:00:00 '
    cmd += ' --numDays=3 '
    cmd += ' --dirName=BillsRTTestExp20jan98 '
    cmd += ' --experimentsDirNum=2 '
    cmd += ' --PI="Bill Rideout" '
    cmd += ' --PIEmail="brideout@mit.edu" '
    cmd += ' --fileAnalyst="John Doe,Tom Sawyer" '
    cmd += ' --fileAnalystEmail=jdoe@haystack.mit.edu,tsawyer@haystack.mit.edu '
    
    print('Command to be tested: <%s>' % (cmd))
    result = os.system(cmd)
    if result == 0:
        print('Test of createRTExp.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')

    #### test of changeExpStatus.py ####
    print('Testing changeExpStatus.py ...')
    cmd = os.path.join(binDir, 'changeExpStatus.py')
    expDir = os.path.join(expBase2, '1998/mlh', 'BillsTestExp20jan98')
    expBaseDir = os.path.join('experiments2', '1998/mlh', 'BillsTestExp20jan98')
    cmd += ' --expDir=%s ' % (expDir)
    cmd += ' --expName="Bill Rideout World Day modified test experiment" '
    cmd += ' --siteID=%i ' % (madDBObj.getSiteID())
    cmd += ' --startDate=1998-01-20 '
    cmd += ' --startTime=12:00:00 '
    cmd += ' --endDate=1998-01-21 '
    cmd += ' --endTime=12:00:00 '
    cmd += ' --inst=31 '
    cmd += ' --security=1 '
    cmd += ' --PI="Bill Rideout" '
    cmd += ' --PIEmail="brideout@mit.edu" '
    print('Command to be tested: <%s>' % (cmd))
    result = os.system(cmd)
    if result == 0:
        print('Test of changeExpStatus.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')
    
    
    ### register with this experiment ###
    madUserObj.registerExperiment(email, expBaseDir)


    #### test of addFileToExp.py ####
    print('Testing addFileToExp.py ...')
    shutil.copy('/tmp/mlh980120g.002.hdf5', '/tmp/mlh980120g.003.hdf5')
    cmd = os.path.join(binDir, 'addFileToExp.py')
    cmd += ' --madFilename=/tmp/mlh980120g.003.hdf5 '
    cmd += ' --expDir=%s ' % (expDir)
    cmd += ' --permission=0 '
    cmd += ' --fileDesc="Another test" '
    cmd += ' --category=2 '
    cmd += ' --kindat=3408 '
    cmd += ' --fileAnalyst="Bill Rideout" '
    cmd += ' --fileAnalystEmail=brideout@mit.edu '
    cmd += ' --createCachedText '
    cmd += ' --createCachedNetCDF4 '
    
    print('Command to be tested: <%s>' % (cmd))
    result = os.system(cmd)
    if result == 0:
        print('Test of addFileToExp.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')


    #### test of updateFileInExp.py ####
    print('Testing updateFileInExp.py ...')
    cmd = os.path.join(binDir, 'updateFileInExp.py')
    cmd += ' --madFilename=/tmp/mlh980120g.003.hdf5 '
    cmd += ' --expDir=%s ' % (expDir)
    print('Command to be tested: <%s>' % (cmd))
    result = os.system(cmd)
    if result == 0:
        print('Test of updateFileInExp.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')

    #### test of changeFileStatus.py ####
    print('Testing changeFileStatus.py ...')
    cmd = os.path.join(binDir, 'changeFileStatus.py')
    cmd += ' --filename=mlh980120g.003.hdf5 '
    cmd += ' --expDir=%s ' % (expDir)
    cmd += ' --permission=1 '
    cmd += ' --fileDesc="Yet another file description" '
    cmd += ' --category=3 '
    cmd += ' --fileAnalyst="John Doe" '
    cmd += ' --fileAnalystEmail=jdoe@haystack.mit.edu '
    result = os.system(cmd)
    if result == 0:
        print('Test of changeFileStatus.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')

    #### test of removeFileFromExp.py ####
    print('Testing removeFileFromExp.py ...')
    cmd = os.path.join(binDir, 'removeFileFromExp.py')
    cmd += ' --filename=mlh980120g.003.hdf5 '
    cmd += ' --expDir=%s ' % (expDir)
    result = os.system(cmd)
    if result == 0:
        print('Test of removeFileFromExp.py succeeded.\n')
    else:
        print('Error - regression test aborting...')
        raise ValueError('')
    

    print('SUCCESS - check for two experiment notification and XXXX instrument emails send to %s' % (email))

except ValueError:
    print('FAILURE')
except:
    traceback.print_exc()
    print('FAILURE')


### final clean up ###
try:
    thisExp = os.path.join(expBase, '1998/mlh', 'BillsTestExp20jan98')
    os.system('rm -rf %s' % (thisExp))
    thisExp = os.path.join(expBase, '1998/mlh', 'BillsRTTestExp20jan98')
    os.system('rm -rf %s' % (thisExp))
    thisExp = os.path.join(expBase2, '1998/mlh', 'BillsTestExp20jan98')
    os.system('rm -rf %s' % (thisExp))
    thisExp = os.path.join(expBase2, '1998/mlh', 'BillsRTTestExp20jan98')
    os.system('rm -rf %s' % (thisExp))
    os.system('rm /tmp/mlh98*')
    madUserObj.unregisterExperiment(email, expBaseDir)
except:
    pass




