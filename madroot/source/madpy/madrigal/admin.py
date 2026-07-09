"""The admin module contains all administrative classes relating to the madrigal python api.

The main role of this module is to update the data in the Madrigal database.  Also contains a
notification class and a standard error handing class.

$Id: admin.py 7690 2024-09-05 19:42:13Z brideout $
"""
# standard python imports
import os, os.path, sys
import smtplib, email.message
import datetime, time
import types
import traceback
import shutil
import hashlib
import urllib
import re
import glob
import warnings
import subprocess
import hashlib

# third party inports
import numpy

# Madrigal imports
import madrigal.metadata
import madrigal.openmadrigal
import madrigal.cedar
import madrigal.data
import madrigal.ui.userData

def convertMad2FileToMad3(mad2File, madDB=None, status=None):
    """convertMad2FileToMad3 will convert an input mad2File to Madrigal 3 HDF5.  It returns the path to the
    newly creates file, which will be in the /tmp directory.
    
    Inputs:
    
        mad2File - A Madrigal 2 format file to convert
        
        madDB - a madrigal.metadata.MadrigalDB object.  If None (the default) created.
        
        status - if None, get status from fileTab.txt.  Else use status passed in
        
    Returns: full path to newly created Madrigal 3 Hdf5 file.  Basename is basename of input file, with .hdf5 extension
    """
    if madDB is None:
        madDB = madrigal.metadata.MadrigalDB()
        
    # make sure an hdf5 file not passed in
    base, ext = os.path.splitext(mad2File)
    if ext in ('.hdf5', '.h5', '.hdf5'):
        raise ValueError('Cannot call convertMad2FileToMad3 with Hdf5 file %s' % (mad2File))
        
    madDataObj = madrigal.data.MadrigalFile(mad2File, madDB)
    kinst = madDataObj.getKinstList()[0]
    kindat = madDataObj.getKindatList()[0]
    
    extraParms, indParms, splitParms = madDB.getKinstKindatConfig(kinst, kindat)
    
    tmpFile = os.path.join('/tmp', os.path.basename(mad2File) + '.hdf5')
    # make sure it doesn't exist
    if os.access(tmpFile, os.R_OK):
        os.remove(tmpFile)
    
    madDataObj.exportToHdf(tmpFile, indParms, splitParms, extraParms, status=status)
    
    return(tmpFile)
    
    


class MadrigalDBAdmin:
    """MadrigalDBAdmin is a class that allows modifications to be made to the Madrigal database

    dbAdminObj = madrigal.admin.MadrigalDBAdmin()

    expDir = dbAdminObj.createMadrigalExperiment('/home/hyperion/brideout/mlh050429c.000',
                                        'Dummy experiment',
                                        0,
                                        'test exp',
                                        30,
                                        1)

    Non-standard Python modules used: None

    Change history:

    Written by "Bill Rideout":mailto:wrideout@haystack.mit.edu  May. 5, 2005

    """
    
    def __init__(self, madDB = None):
        """__init__ initializes MadrigalDBAdmin
        
        Inputs: madDB - Existing MadrigalDB object.  Default = None.
        
        Returns: void

        Affects:

            Sets self.__madDB to MadrigalDB object
            Sets self.__madInst to MadrigalInstrument object
        """

        if madDB == None:
            self.__madDB = madrigal.metadata.MadrigalDB()
        else:
            self.__madDB = madDB

        self.__madInst = madrigal.metadata.MadrigalInstrument(self.__madDB)
        self.__openMad = madrigal.openmadrigal.OpenMadrigal(self.__madDB)
        self.__madSite = madrigal.metadata.MadrigalSite(self.__madDB)
        self._userData = madrigal.ui.userData.MadrigalUserData(self.__madDB)
        
            

    def createRTExperiment(self,
                           startTime,
                           numDays,
                           instrument,
                           expTitle,
                           rtFilenameList,
                           kindatList,
                           permissionList,
                           fileDescList,
                           optChar = '',
                           endTime = None,
                           security = 0,
                           dirName = None,
                           experimentsDirNum=None,
                           PI='', PIEmail='', 
                           fileAnalystList=None, fileAnalystEmailList=None,
                           notify = True,
                           allowNonHdf5=False):
        """createRTExperiment creates a new experiment on Madrigal in preparation for realtime data.

        Since the experiment is presumably not yet complete, metadata such as the duration of the experiment
        must be estimated.  This metadata will be overwritten when the first batch file is added.

        Inputs:
        
            startTime - experiment start time.  If a number, assumed to be seconds since 1/1/1970.  May also
            be a datetime.datetime object
            
            numDays - number of days the experiment is estimated to run.  Ignored if optional endTime given.
            
            instrument - instrument code or 3-letter Madrigal mnenonic
            
            expTitle - experiment title
            
            rtFilenameList - list of realtime filenames to be created. Must all be Hdf5 files.
            
            kindatList - list of ints of kindats for each realtime file.  Len = len(rtFilenameList)
            
            permissionList - list of 0 (public) or 1 (private). Len = len(rtFilenameList)
            
            fileDescList - list of realtime file descriptions

            optChar - optional character to be added to experiment directory if no dirName
                      given.  If dirName argument given, this argument ignored.  optChar
                      is used if the default directory name DDmmmYY is used for
                      more than one experiment created for a given instrument on a given day.
                      For example, if --optChar=h for a MLH experiment on September 12, 2005,
                      then the experiment directory created would be experiments/2005/mlh/12sep05h.

            endTime - optional end date and time of experiment.  If a number, assumed to be seconds since
            1/1/1970.  May also be a datetime.datetime object

            security - experiment security setting.  If 0 (the default) public.  If 1, private.
                       If -1, entire experiment ignored.  Any given file permission is the more
                       restricted of experiment permission and file permission.

            dirName - directory name to use for experiment.  If None (the default), the directory
                      name will be the default name DDmmmYY[optChar].  Cannot contain "/"
                      
            experimentsDirNum - the number to be appended to the experiments directory, if experiments
                      directory being used is of the form experiments[0-9]* instead of just
                      experiments.  For example, if experimentsDirNum is 7, then the experiment
                      would be created in MADROOT/experiments7 instead of MADROOT/experiments.
                      
            PI- full name of principal investigator.  The default is ''
            
            PIEmail - email of principal investigator.  The default is ''
            
            fileAnalystList - list of full names of file analysts, one for each file.  If None, the default, 
                File Analyst = ''
            
            fileAnalystEmailList - list of emails of file analysts, one for each file.  If None, the default, 
                File Analyst email = ''
                
            notify - if True (the default), send a message to all registered users.  If False, do not.
            
            allowNonHdf5 - if True, allow filenames without hdf5 extension.  Default is False, do not allow.

        Returns:

            Full path to directory created
            
        """
        # check optChar
        if type(optChar) not in (bytes, str):
            raise ValueError('optChar must be an empty or a one character string, not %s' % (str(optChar)))

        if len(optChar) > 1:
            raise ValueError('optChar must be an empty or a one character string, not %s' % (str(optChar)))

        security = int(security)
        if security not in (-1,0,1):
            raise ValueError('security must be -1, 0, or 1, not %i' % (security))
        
        # convert startTime to datetime if needed
        if type(startTime) in (int, int, float):
            startTime = datetime.datetime.fromtimestamp(startTime, datetime.UTC)

        # create endTime based on numDays
        if endTime != None:
            if type(endTime) in (int, int, float):
                endTime = datetime.datetime.fromtimestamp(startTime, datetime.UTC)
        else:
            if numDays >= 0:
                endTime = startTime + datetime.timedelta(numDays) - datetime.timedelta(0,1)
            else:
                raise ValueError('numDays must not be negative')

        if startTime >= endTime:
            raise ValueError('Experiment start time %s after end time %s' % (str(startTime),
                                                                               str(endTime)))
        

        # get instrument mnemonic and instCode
        try:
            instCode = int(instrument)
            instMnemonic = self.__madInst.getInstrumentMnemonic(instCode)
        except ValueError:
            if len(instrument) != 3:
                raise ValueError('%s not a legal instrument mnemonic' % (str(instrument)))
            instMnemonic = instrument.lower()
            # verify its a legal mnemonic
            instList = self.__madInst.getInstrumentList()
            found = False
            for inst in instList:
                if instMnemonic == inst[1]:
                    found = True
                    instCode = inst[2]
                    break
            if found == False:
                raise ValueError('%s not a legal instrument mnemonic or code' % (str(instrument)))

        if instMnemonic == None:
            raise ValueError('%s not a legal instrument mnemonic or code' % (str(instrument)))
        
        instDesc = self.__madInst.getInstrumentName(instCode)

        # expTitle
        if type(expTitle) not in (bytes, str) and expTitle != None:
            raise ValueError('expTitle not a string')
        if expTitle == None:
            expTitle = ''
        if expTitle.find(',') != -1:
            raise ValueError('expTitle cannot contain a comma')
            
        # PI
        if type(PI) not in (bytes, str) and PI != None:
            raise ValueError('PI not a string')
        if PI == None:
            PI = ''
        if PI.find(',') != -1:
            raise ValueError('PI cannot contain a comma')
            
        # PIEmail
        if type(PIEmail) not in (bytes, str) and PIEmail != None:
            raise ValueError('PIEmail not a string')
        if PIEmail == None:
            PIEmail = ''
        if PIEmail.find(',') != -1:
            raise ValueError('PIEmail cannot contain a comma')

        # rtFilenameList
        if type(rtFilenameList) not in (list, tuple):
            raise ValueError('rtFilenameList not a list or tuple')
        # make sure each rtFilename is a string without /
        for filename in rtFilenameList:
            if type(filename) not in (bytes, str):
                raise ValueError('rtFilenameList must contain strings')
            if filename.find('/') != -1:
                raise ValueError('rtFilenameList must contain strings without /')
            if filename.find(',') != -1:
                raise ValueError('filename cannot contain a comma')
            base, ext = os.path.splitext(filename)
            if ext not in ('.hdf5', '.h5', '.hdf5') and not allowNonHdf5:
                raise ValueError('All input files must have a valid Hdf5 extension, <%s> does not' % (filename))

        # kindatList
        if len(kindatList) != len(rtFilenameList):
            raise ValueError('length of kindatList not equal length of rtFilenameList')
        for item in kindatList:
            try:
                int(item)
            except:
                raise ValueError('kindatList must contain integers')

        # permissionList
        if len(permissionList) != len(rtFilenameList):
            raise ValueError('length of permissionList not equal length of rtFilenameList')
        for item in permissionList:
            try:
                permission = int(item)
            except:
                raise ValueError('permissionList must contain integers')

            if permission not in (0,1):
                raise ValueError('permissionList must contain integers of value 0 (public) or 1 (private)')

        
        # fileDescList
        if len(fileDescList) != len(rtFilenameList):
            raise ValueError('length of fileDescList not equal length of rtFilenameList')
        for item in fileDescList:
            if type(item) not in (bytes, str):
                raise ValueError('fileDescList must only contain strings')
            if item.find(',') != -1:
                raise ValueError('fileDesc cannot contain a comma')
            
        # fileAnalystList
        if fileAnalystList:
            if len(fileAnalystList) != len(rtFilenameList):
                raise ValueError('length of fileAnalystList not equal length of rtFilenameList')
            for item in fileAnalystList:
                if type(item) not in (bytes, str):
                    raise ValueError('fileAnalystList must only contain strings')
                if item.find(',') != -1:
                    raise ValueError('fileAnalyst cannot contain a comma')
                
        # fileAnalystEmailList
        if fileAnalystEmailList:
            if len(fileAnalystEmailList) != len(rtFilenameList):
                raise ValueError('length of fileAnalystEmailList not equal length of rtFilenameList')
            for item in fileAnalystEmailList:
                if type(item) not in (bytes, str):
                    raise ValueError('fileAnalystEmailList must only contain strings')
                if item.find(',') != -1:
                    raise ValueError('fileAnalystEmail cannot contain a comma')
            
        # experimentDirNum
        if experimentsDirNum != None:
            experimentsDir = 'experiments%i' % (experimentsDirNum)
            # verify this directory exists
            if not os.access(os.path.join(self.__madDB.getMadroot(), experimentsDir), os.R_OK):
                raise ValueError('no such directory %s' % (experimentsDir))
        else:
            experimentsDir = 'experiments'

        # all the arguments check out - create the directory
        # create experiment dir
        expDir2 = os.path.join('%i' % (startTime.year),
                               instMnemonic)
        
        if dirName == None:
            dirName = startTime.strftime('%d%b%y').lower() + optChar
        else:
            # verify dirName is basename
            if dirName.find('/') != -1:
                raise ValueError('dirName must be base directory name, not %s' % (dirName))

        expDir2 = os.path.join(expDir2, dirName)

        expDir = os.path.join(self.__madDB.getMadroot(), experimentsDir, expDir2)
        
        expDir3 = os.path.join(experimentsDir, expDir2)

        # if the directory already exists, raise error
        if os.access(expDir, os.R_OK):
            raise IOError('Directory %s already exists' % (expDir))

        os.makedirs(expDir)
        os.chmod(expDir, 0o775)

        # expTab.txt
        expTabText = '0,' + self.__madDB.getTopLevelUrl()
        if expTabText[-1] != '/':
            expTabText += '/madtoc/'
        else:
            expTabText += 'madtoc/'
        expTabText += '%s,%s,%i,%04i%02i%02i,%02i%02i%02i,%04i%02i%02i,%02i%02i%02i,%i,%i,%s,%s\n' %(expDir3,
                                                                                                     expTitle,
                                                                                                     self.__madDB.getSiteID(),
                                                                                                     startTime.year,
                                                                                                     startTime.month,
                                                                                                     startTime.day,
                                                                                                     startTime.hour,
                                                                                                     startTime.minute,
                                                                                                     startTime.second,
                                                                                                     endTime.year,
                                                                                                     endTime.month,
                                                                                                     endTime.day,
                                                                                                     endTime.hour,
                                                                                                     endTime.minute,
                                                                                                     endTime.second,
                                                                                                     instCode,
                                                                                                     security,
                                                                                                     PI,
                                                                                                     PIEmail)

        # write expTab.txt
        f = open(os.path.join(expDir, 'expTab.txt'), 'w', encoding='utf-8')
        f.write(expTabText)
        f.close()
        os.chmod(os.path.join(expDir, 'expTab.txt'), 0o664)

        # fileTab.txt
        # set file times to right now UT
        nowUT = datetime.datetime.utcnow()
        nowDate = nowUT.strftime('%Y%m%d')
        nowTime = nowUT.strftime('%H%M%S')
        fileTabText = ''
        for index in range(len(rtFilenameList)):
            
            if fileAnalystList and fileAnalystEmailList:
                fileAnalyst = fileAnalystList[index]
                fileAnalystEmail = fileAnalystEmailList[index]
            else:
                fileAnalyst = ''
                fileAnalystEmail = ''
            
            fileTabText += rtFilenameList[index]
            fileTabText += ',0,%i,4,0,0,0,%s,%s,' % (kindatList[index], nowDate, nowTime)
            fileTabText += '%s,%i,%s,%s\n' % (fileDescList[index], permissionList[index],
                                              fileAnalyst, fileAnalystEmail)

        # write fileTab.txt
        f = open(os.path.join(expDir, 'fileTab.txt'), 'w')
        f.write(fileTabText)
        f.close()
        os.chmod(os.path.join(expDir, 'fileTab.txt'), 0o664)

        # create all writeable directory overview
        os.makedirs(os.path.join(expDir, 'overview'))
        os.chmod(os.path.join(expDir, 'overview'), 0o777)
        
        if notify:
            # get expPath without MAD ROOT
            expPath = expDir[expDir.find('experiments'):]
            if expPath[-1] == '/':
                expPath = expPath[:-1]
            madNotify = MadrigalNotify(self.__madDB)
            message = 'You requested to be notified when new data from instrument %s was available. A new realtime experiment for that instrument has been created at %s at %s. '   \
                % (instDesc, self.__madDB.getTopLevelUrl(), str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            message += 'Please contact %s if you wish to be unregistered.' %  (self.__madDB.getContactEmail())
                
            # deal with users registered for instrument in general
            userList = self._userData.getRegisteredInstUsers(instCode)
            if len(userList) > 0:
                for user in userList:
                    try:
                        madNotify.notify(user, message, 'Update to Madrigal instrument you registered interest in')
                    except:
                        print(('Warning - email to %s failed to be sent' % (user)))

        return(expDir)
        
        
    def writeRTMadrigalFile(self,
                            expDir,
                            rtFilename,
                            rtFile):
        """writeRTMadrigalFile writes a realtime Madrigal file to a Madrigal experiment directory.

        Fails if rtFilename does not match one listed in fileTab.txt.

        Inputs:
        
            expDir - full path to experiment directory (as returned by createRTExperiment)
            
            rtFilename - basename of realtime file to be writtem
            
            rtFile - a string containing the realtime file contents

        Returns: None

        Raises exception if rtFilename does not match one listed in fileTab.txt.
        """
        # verify rtFilename listed in fileTab.txt
        try:
            fileInfo = madrigal.metadata.MadrigalMetaFile(self.__madDB, os.path.join(expDir, 'fileTab.txt'))
        except:
            raise ValueError('Unable to open fileTab.txt in %s' % (expDir))
        
        if fileInfo.getHasCatalogByFilename(rtFilename) == None:
            raise ValueError('Filename %s not found in fileTab.txt' % (rtFilename))

        # okay - write it
        f = open(os.path.join(expDir, rtFilename), 'w', encoding='utf-8')
        f.write(rtFile)
        f.close()
        os.chmod(os.path.join(expDir, rtFilename), 0o664)


    def appendRTMadrigalFile(self,
                             expDir,
                             rtFilename,
                             rtFile):
        """appendRTMadrigalFile used to allow appending to a realtime Madrigal file. No longer possible with Hdf5 format.

        Inputs:
        
            expDir - full path to experiment directory (as returned by createRTExperiment)
            
            rtFilename - basename of realtime file to be writtem
            
            rtFile - a string containing the new realtime file contents

        Always raises IOError
        """
        raise IOError('The method appendRTMadrigalFile no longer supported by Madrigal 3.0')
        


    def createMadrigalExperiment(self,
                                 madFilename,
                                 expTitle,
                                 permission,
                                 fileDesc,
                                 instCode = None,
                                 category = 1,
                                 optChar = '',
                                 dirName = None,
                                 kindat = None,
                                 experimentsDirNum=None,
                                 PI='', PIEmail='', 
                                 fileAnalyst='', fileAnalystEmail='',
                                 createCachedText=False, createCachedNetCDF4=False,
                                 notify = True, updateToMad3=False):
        """createMadrigalExperiment creates a new experiment on Madrigal using metadata read from madFilename.

        Inputs:
        
            madFilename - full path to the complete Madrigal file.  Basename will be maintained.
            
            expTitle - experiment title
            
            permission - 0 (public) or 1 (private) or -1 (ignore). 
            
            fileDesc - file description

            instCode - instrument code.  If default (None), instrument code is taken from file, but error
            is thrown if more than one kinst found.

            category - 1=default, 2=variant, 3=history, or 4=realtime. Default is 1 (default file)

            optChar - optional character to be added to experiment directory if no dirName
                      given.  If dirName argument given, this argument ignored.  optChar
                      is used if the default directory name DDmmmYY is used for
                      more than one experiment created for a given instrument on a given day.
                      For example, if --optChar=h for a MLH experiment on September 12, 2005,
                      then the experiment directory created would be experiments/2005/mlh/12sep05h.

            dirName - directory name to use for experiment.  If None (the default), the directory
                      name will be the default name DDmmmYY[optChar].  Cannot contain "/"

            kindat - if not None (the default), use this kindat instead of what is found in the file.
            
            experimentsDirNum - the number to be appended to the experiments directory, if experiments
                      directory being used is of the form experiments[0-9]* instead of just
                      experiments.  For example, if experimentsDirNum is 7, then the experiment
                      would be created in MADROOT/experiments7 instead of MADROOT/experiments.
                      
            PI- full name of principal investigator.  The default is ''
            
            PIEmail - email of principal investigator.  The default is ''
            
            fileAnalyst -full name of file analyst.  The default is ''
            
            fileAnalystEmail - email of file analyst,.  The default is ''
            
            createCachedText - if True, add cached text file in overview/<basename>.txt.gz.  If False,
                no cached file.
                
            createCachedNetCDF4 - if True, add cached netCDF4 file in overview/<basename>.nc.  If False,
                no cached file.
                
            notify - if True (the default), send a message to all registered users.  If False, do not.
            
            updateToMad3 - if False (the default), error raised if madFilename non-Hdf5 file. If True, try to
                convert madFilename to Madrigal with .hdf5 extension before loading.
            
        Returns:

            Full path to directory created
            
        """
        # check optChar
        if type(optChar) not in (bytes,str):
            raise ValueError('optChar must be an empty or a one character string, not %s' % (str(optChar)))

        if len(optChar) > 1:
            raise ValueError('optChar must be an empty or a one character string, not %s' % (str(optChar)))
        
        base, ext = os.path.splitext(madFilename)
        if updateToMad3:
            if ext not in ('.hdf5', '.h5', '.hdf5'):
                madFilename = convertMad2FileToMad3(madFilename, self.__madDB, fileDesc)
        elif ext not in ('.hdf5', '.h5', '.hdf5'):
            raise ValueError('called createMadrigalExperiment with non-Hdf5 file <%s> and updateToMad3 False' \
                % (madFilename))
                
        fileInfo = madrigal.data.MadrigalFile(madFilename, self.__madDB)

        # get startTime
        sTime = fileInfo.getEarliestTime()
        startTime = datetime.datetime(sTime[0],sTime[1],sTime[2],sTime[3],sTime[4],sTime[5])

        # get endTime
        eTime = fileInfo.getLatestTime()
        endTime = datetime.datetime(eTime[0],eTime[1],eTime[2],eTime[3],eTime[4],eTime[5])
        
        # get instrument mnemonic and instCode
        if instCode == None:
            kinstList = fileInfo.getKinstList()
            if len(kinstList) == 0:
                raise ValueError('No kinst values found in file')
            if len(kinstList) > 1:
                raise ValueError('More than one kinst value found in file: %s' % (str(kinstList)))
            instCode = kinstList[0]
        instMnemonic = self.__madInst.getInstrumentMnemonic(instCode)
        instDesc = self.__madInst.getInstrumentName(instCode)
        if instMnemonic == None:
            raise ValueError('Unable to find mnemonic for kinst %i' % (instCode))

        # expTitle
        if type(expTitle) not in (bytes, str) and expTitle != None:
            raise ValueError('expTitle not a string')
        if expTitle == None:
            expTitle = ''
        if expTitle.find(',') != -1:
            raise ValueError('expTitle cannot contain a comma')

        # kindat
        if kindat == None:
            kindatList = fileInfo.getKindatList()
            if len(kindatList) == 0:
                raise ValueError('No kindat values found in file')
            if len(kindatList) > 1:
                raise ValueError('More than one kindat value found in file: %s' % (str(kindatList)))
            kindat = kindatList[0]
        else:
            kindat = int(kindat)

        # permission
        if permission not in (0,1, -1):
            raise ValueError('permission must be either 0 or 1 or -1, not %s' % (str(permission)))

        # fileDesc
        if type(fileDesc) not in  (bytes, str) and fileDesc != None:
            raise ValueError('fileDesc not a string')
        if fileDesc == None:
            fileDesc = ''
        if fileDesc.find(',') != -1:
            raise ValueError('fileDesc cannot contain a comma')

        # category
        if category not in (1,2,3,4):
            raise ValueError('category must be 1=default, 2=variant, 3=history, or 4=realtime; not %s' % (str(category)))

        # hasCatalog and hasHeader
        catStr = fileInfo.getCatalogHeaderStr()
        if len(catStr) > 0:
            hasCatalog = 1
            hasHeader = 1
        else:
            hasCatalog = 0
            hasHeader = 0
            
        # experimentDirNum
        if experimentsDirNum != None:
            experimentsDir = 'experiments%i' % (experimentsDirNum)
            # verify this directory exists
            if not os.access(os.path.join(self.__madDB.getMadroot(), experimentsDir), os.R_OK):
                raise ValueError('no such directory %s' % (experimentsDir))
        else:
            experimentsDir = 'experiments'
            
        # PI
        if type(PI) not in (bytes, str) and PI != None:
            raise ValueError('PI not a string')
        if PI == None:
            PI = ''
        if PI.find(',') != -1:
            raise ValueError('PI cannot contain a comma')
            
        # PIEmail
        if type(PIEmail) not in (bytes, str) and PIEmail != None:
            raise ValueError('PIEmail not a string')
        if PIEmail == None:
            PIEmail = ''
        if PIEmail.find(',') != -1:
            raise ValueError('PIEmail cannot contain a comma')
            
        # fileAnalyst
        if type(fileAnalyst) not in (bytes, str) and fileAnalyst != None:
            raise ValueError('fileAnalyst not a string')
        if fileAnalyst == None:
            fileAnalyst = ''
        if fileAnalyst.find(',') != -1:
            raise ValueError('fileAnalyst cannot contain a comma')
            
        # fileAnalystEmail
        if type(fileAnalystEmail) not in (bytes, str) and fileAnalystEmail != None:
            raise ValueError('fileAnalystEmail not a string')
        if fileAnalystEmail == None:
            fileAnalystEmail = ''
        if fileAnalystEmail.find(',') != -1:
            raise ValueError('fileAnalystEmail cannot contain a comma')
        
        # all the arguments check out - create the directory
        # create experiment dir
        expDir2 = os.path.join('%i' % (startTime.year),
                              instMnemonic)
        
        if dirName == None:
            dirName = startTime.strftime('%d%b%y').lower() + optChar
        else:
            # verify dirName is basename
            if dirName.find('/') != -1:
                raise ValueError('dirName must be base directory name, not %s' % (dirName))
            
        expDir2 = os.path.join(expDir2, dirName)

        expDir = os.path.join(self.__madDB.getMadroot(), experimentsDir, expDir2)
        
        expDir3 = os.path.join(experimentsDir, expDir2)

        # if the directory already exists, raise error
        if os.access(expDir, os.R_OK):
            raise IOError('Directory %s already exists' % (expDir))

        os.makedirs(expDir)
        os.chmod(expDir, 0o775)

        # expTab.txt
        expTabText = '0,' + self.__madDB.getTopLevelUrl()
        if expTabText[-1] != '/':
            expTabText += '/madtoc/'
        else:
            expTabText += 'madtoc/'
        expTabText += '%s,%s,%i,%04i%02i%02i,%02i%02i%02i,%04i%02i%02i,%02i%02i%02i,%i,%i,%s,%s\n' %(expDir3,
                                                                                                     expTitle,
                                                                                                     self.__madDB.getSiteID(),
                                                                                                     startTime.year,
                                                                                                     startTime.month,
                                                                                                     startTime.day,
                                                                                                     startTime.hour,
                                                                                                     startTime.minute,
                                                                                                     startTime.second,
                                                                                                     endTime.year,
                                                                                                     endTime.month,
                                                                                                     endTime.day,
                                                                                                     endTime.hour,
                                                                                                     endTime.minute,
                                                                                                     endTime.second,
                                                                                                     instCode,
                                                                                                     permission,
                                                                                                     PI, PIEmail)

        # write expTab.txt
        f = open(os.path.join(expDir, 'expTab.txt'), 'w', encoding='utf-8')
        f.write(expTabText)
        f.close()
        os.chmod(os.path.join(expDir, 'expTab.txt'), 0o664)

        # fileTab.txt
         # set file times to right now UT
        nowUT = datetime.datetime.utcnow()
        nowDate = nowUT.strftime('%Y%m%d')
        nowTime = nowUT.strftime('%H%M%S')
        fileTabText = os.path.basename(madFilename)
        fileTabText += ',0,%i,%i,0,%i,%i,%s,%s,' % (kindat,category,hasCatalog,hasHeader,nowDate,nowTime)
        fileTabText += '%s,%i,%s,%s\n' % (fileDesc, permission,
                                          fileAnalyst, fileAnalystEmail)

        # write fileTab.txt
        f = open(os.path.join(expDir, 'fileTab.txt'), 'w', encoding='utf-8')
        f.write(fileTabText)
        f.close()
        os.chmod(os.path.join(expDir, 'fileTab.txt'), 0o664)

        # create all writeable directory overview
        os.makedirs(os.path.join(expDir, 'overview'))
        os.chmod(os.path.join(expDir, 'overview'), 0o777)

        # cp madFilename to new directory
        shutil.copy2(madFilename, os.path.join(expDir, os.path.basename(madFilename)))
        os.chmod(os.path.join(expDir, os.path.basename(madFilename)), 0o664)

        # populate overview
        overviewFile = os.path.join(os.path.dirname(madFilename), 'overview', os.path.basename(madFilename) + '.summary')
        if os.access(overviewFile, os.R_OK):
            # make sure overview exist
            overviewDir = os.path.join(expDir, 'overview')
            if not os.access(overviewDir, os.W_OK):
                os.mkdir(overviewDir)
                os.chmod(overviewDir, 0o777)
            shutil.copy2(overviewFile, overviewDir)
        else:
            fileInfo = madrigal.data.MadrigalFile(os.path.join(expDir, os.path.basename(madFilename)), self.__madDB,
                                                  acceptOldSummary=acceptOldSummary)
        
        if createCachedText:
            cachedName = os.path.join(expDir, 'overview', os.path.basename(madFilename) + '.txt')
            madrigal.cedar.convertToText(madFilename, cachedName)
            subprocess.check_call(['gzip', cachedName])
            
        if createCachedNetCDF4:
            cachedName = os.path.join(expDir, 'overview', os.path.basename(madFilename) + '.nc')
            madrigal.cedar.convertToNetCDF4(madFilename, cachedName)
        
        if notify:
            # get expPath without MAD ROOT
            expPath = expDir[expDir.find('experiments'):]
            if expPath[-1] == '/':
                expPath = expPath[:-1]
            madNotify = MadrigalNotify(self.__madDB)
            message = 'You requested to be notified when the instrument %s from the Madrigal site %s was updated. A new experiment at %s was created on %s.'  \
                % (instDesc, self.__madDB.getTopLevelUrl(), expDir3, str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            message += 'Please contact %s if you wish to be unregistered.' % (self.__madDB.getContactEmail())
                
            # deal with users registered for instrument in general
            userList = self._userData.getRegisteredInstUsers(instCode)
            if len(userList) > 0:
                for user in userList:
                    try:
                        madNotify.notify(user, message, 'Update to Madrigal instrument data you registered interest in')
                    except:
                        print(('Warning - email to %s failed to be sent' % (user)))

        return(expDir)



    def changeExpStatus(self,
                        expDir,
                        expUrl=None,
                        expName = None,
                        siteID = None,
                        startDatetime = None,
                        endDatetime = None,
                        inst = None,
                        security = None,
                        PI = None,
                        PIEmail = None):
        """changeExpStatus is used to change attributes in expTab.txt.  If None, no change.

        Inputs:
        
            expDir - full path to experiment directory. Required.  Example:
               "/opt/madrigal/experiments/1998/mlh/20jan98". If None, do not change.
            
            expUrl - must be in form <cgi base>/madtoc/YYYY/<3 letter lower case inst code>/<expDir>
                       example: http://www.haystack.mit.edu/cgi-bin/madtoc/1997/mlh/03dec97g.
                       If None, do not change.

            expName - experiment name.  Quotes required if contains spaces.  Example: "World Day"
                        If None, do not change.

            siteID - Madrigal siteID (int) of where data will be stored.  Error raised if not the siteID
                       of the local Madrigal site. Example: 4. If None, do not change.

            startDatetime - new start datetime of experiment (UT). If None, do not change.

            endDatetime - new end datetime of experiment (UT). If None, do not change.

            inst - new instrument code (int).  Example: 30. If None, do not change.  Prints
                    warning if not found in instTab.txt

            security - new security code.  Allowed values are 0 for public, 1 for private (limited IP range access)
                    -1 for ignore, 2 for archived experiment, 3 for private (limited IP range access) archived
                    experiment. If None, do not change.
                    
            PI - name of PI. If None, no change
            
            PIEmail - PI email.  If None, no change
            
        """
        try:
            expTabInfo = madrigal.metadata.MadrigalExperiment(self.__madDB, os.path.join(expDir, 'expTab.txt'))
        except:
            raise ValueError('Unable to open expTab.txt in %s' % (expDir))

        # be sure only one experiment
        if expTabInfo.getExpCount() != 1:
            raise ValueError('expTab.txt in %s has %i experiments, should have exactly 1' % (expDir,
                                                                                              expTabInfo.getExpCount()))

        # expUrl
        if expUrl != None:
            # print warning if not this directory
            index = expUrl.find('/madtoc/')
            thisDir = expUrl[index+8:]
            if thisDir[-1] == '/':
                thisDir = thisDir[:-1]
            if expDir.find(thisDir) == -1:
                raise ValueError('The experiment url you are setting this experiment to <%s> conflicts with experiment directory %s' % (expUrl, expDir))
            expTabInfo.setExpUrlByPosition(0, expUrl)

        # expName
        if expName != None:
            expTabInfo.setExpNameByPosition(0, expName)

        # siteID
        if siteID != None:
            siteID = int(siteID)
            if siteID != self.__madDB.getSiteID():
                raise ValueError('Setting experiment to a siteID %i different from this site\'s id %i' % (siteID,
                                                                                                                    self.__madDB.getSiteID()))
            expTabInfo.setExpSiteIdByPosition(0, siteID)

        # startDatetime
        if startDatetime != None:
            # verify before endDatetime if that also being set
            if endDatetime != None:
                if startDatetime > endDatetime:
                    raise ValueError('startDatetime %s must be before endDatetime %s' % (str(startDatetime),
                                                                                          str(endDatetime)))
            expTabInfo.setExpStartDateTimeByPosition(startDatetime, 0)

        # endDatetime
        if endDatetime != None:
            expTabInfo.setExpEndDateTimeByPosition(endDatetime, 0)

        # inst
        if inst != None:
            inst = int(inst)
            if self.__madInst.getInstrumentName(inst) == None:
                print('WARNING: instrument %i not found in instTab.txt' % (inst))
            expTabInfo.setExpKinstByPosition(0, inst)

        # security
        if security != None:
            security = int(security)
            if security not in (-1, 0, 1, 2, 3):
                raise ValueError('security must be in (-1, 0, 1, 2, 3), not %i' % (inst))
            expTabInfo.setSecurityByPosition(0, security)
            
        # PI
        if PI != None:
            expTabInfo.setPIByPosition(0, PI)
            
        # PIEmail
        if PIEmail != None:
            expTabInfo.setPIEmailByPosition(0, PIEmail)

        # everything successfully changed - write new values
        expTabInfo.writeMetadata()
        
            

    def addMadrigalFile(self,
                        expDir,
                        madFilename,
                        permission,
                        fileDesc,
                        category = 1,
                        kindat = None,
                        notify = True,
                        fileAnalyst = '',
                        fileAnalystEmail = '',
                        createCachedText=False, createCachedNetCDF4=False,
                        updateToMad3=False, acceptOldSummary=False):
        """addMadrigalFile adds a new file to an experiment using metadata read from madFilename.

        Inputs:

            expDir - full path to experiment directory (as returned by createMadriogalExperiment)
        
            madFilename - full path to the complete Madrigal file.  Basename will be maintained.
            
            permission - 0 (public) or 1 (private). 
            
            fileDesc - file description

            category - 1=default, 2=variant, 3=history, or 4=realtime. Default is 1 (default file)

            kindat - if not None (the default), use this kindat instead of what is found in the file.
            
            notify - if True (the default), send a message to all registered users.  If False, do not.
            
            fileAnalyst - full name of file Analyst.  Default is ''
            
            fileAnalystEmail - email of file Analyst.  Default is ''
            
            createCachedText - if True, add cached text file in overview/<basename>.txt.gz.  If False,
                no cached file.
                
            createCachedNetCDF4 - if True, add cached netCDF4 file in overview/<basename>.nc.  If False,
                no cached file.
              
            updateToMad3 - if False (the default), error raised if madFilename non-Hdf5 file. If True, try to
                convert madFilename to Madrigal with .hdf5 extension before loading.
                
            acceptOldSummary - if True, accept an old summary file. Used mainly for upgrading to Madrigal 3. Default
                is False.

        Returns: None
            
        """
        base, ext = os.path.splitext(madFilename)
        if updateToMad3:
            if ext not in ('.hdf5', '.h5', '.hdf5'):
                madFilename = convertMad2FileToMad3(madFilename, self.__madDB, fileDesc)
        elif ext not in ('.hdf5', '.h5', '.hdf5'):
            raise ValueError('called addMadrigalFile with non-Hdf5 file <%s> and updateToMad3 False' \
                % (madFilename))
                
        fileInfo = madrigal.data.MadrigalFile(madFilename, self.__madDB, acceptOldSummary=acceptOldSummary)

        # kindat
        if kindat == None:
            kindatList = fileInfo.getKindatList()
            if len(kindatList) == 0:
                raise ValueError('No kindat values found in file')
            if len(kindatList) > 1:
                raise ValueError('More than one kindat value found in file: %s' % (str(kindatList)))
            kindat = kindatList[0]
        else:
            kindat = int(kindat)

        # permission
        if permission not in (0,1):
            raise ValueError('permission must be either 0 or 1, not %s' % (str(permission)))

        # fileDesc
        if type(fileDesc) not in (bytes, str) and fileDesc != None:
            raise ValueError('fileDesc not a string')
        if fileDesc == None:
            fileDesc = ''
        # check that fileDesc does not illegally contain a comma
        if fileDesc.find(',') != -1:
            raise ValueError('fileDesc string in fileTab.txt cannot contain a comma: <%s> is illegal' % (fileDesc))

        # category
        if category not in (1,2,3,4):
            raise ValueError('category must be 1=default, 2=variant, 3=history, or 4=realtime; not %s' % (str(category)))

        # hasCatalog and hasHeader
        catStr = fileInfo.getCatalogHeaderStr()
        if len(catStr) > 0:
            hasCatalog = 1
            hasHeader = 0
        else:
            hasCatalog = 0
            hasHeader = 0
            
        if fileAnalyst.find(',') != -1:
            raise ValueError('fileAnalyst cannot contain a comma')
        
        if fileAnalystEmail.find(',') != -1:
            raise ValueError('fileAnalystEmail cannot contain a comma')
        

        # all the arguments check out - add line to fileTab.txt
        if not os.access(os.path.join(expDir, 'fileTab.txt'), os.R_OK):
            raise ValueError(' file %s does not yet exist' % (os.path.join(expDir, 'fileTab.txt')))

        # check that this is a new filename
        fileTabObj = madrigal.metadata.MadrigalMetaFile(self.__madDB, os.path.join(expDir, 'fileTab.txt'))
        for i in range(fileTabObj.getFileCount()):
            filename = fileTabObj.getFilenameByPosition(i)
            if filename == os.path.basename(madFilename):
                raise ValueError('File %s already exists - must be deleted first' % (filename))
            

        # fileTab.txt
        nowUT = datetime.datetime.utcnow()
        nowDate = nowUT.strftime('%Y%m%d')
        nowTime = nowUT.strftime('%H%M%S')
        fileTabText = os.path.basename(madFilename)
        fileTabText += ',0,%i,%i,0,%i,%i,%s,%s,' % (kindat,category,hasCatalog,hasHeader,nowDate,nowTime)
        fileTabText += '%s,%i,%s,%s\n' % (fileDesc, permission,
                                          fileAnalyst, fileAnalystEmail)

        # write fileTab.txt
        f = open(os.path.join(expDir, 'fileTab.txt'), 'a')
        f.write(fileTabText)
        f.close()                                                                                                                

        # cp madFilename to new directory
        shutil.copyfile(madFilename, os.path.join(expDir, os.path.basename(madFilename)))
        try:
            os.chmod(os.path.join(expDir, os.path.basename(madFilename)), 0o664)
        except:
            pass

        # populate overview
        overviewFile = os.path.join(os.path.dirname(madFilename), 'overview', os.path.basename(madFilename) + '.summary')
        if os.path.exists(overviewFile):
            # make sure overview exist
            overviewDir = os.path.join(expDir, 'overview')
            if not os.path.exists(overviewDir):
                os.mkdir(overviewDir)
                try:
                    os.chmod(overviewDir, 0o777)
                except:
                    pass
            outfile = os.path.join(overviewDir, os.path.basename(madFilename) + '.summary')
            shutil.copyfile(overviewFile, outfile)
        else:
            fileInfo = madrigal.data.MadrigalFile(os.path.join(expDir, os.path.basename(madFilename)), self.__madDB,
                                                  acceptOldSummary=acceptOldSummary)
                
        if createCachedText:
            cachedName = os.path.join(expDir, 'overview', os.path.basename(madFilename) + '.txt')
            madrigal.cedar.convertToText(madFilename, cachedName)
            subprocess.check_call(['gzip', cachedName])
            
        if createCachedNetCDF4:
            cachedName = os.path.join(expDir, 'overview', os.path.basename(madFilename) + '.nc')
            madrigal.cedar.convertToNetCDF4(madFilename, cachedName)

        # update expTab.txt against all registered files
        self.updateExpTab(expDir)
        
        
        if notify:
            # get expPath without MAD ROOT
            expPath = expDir[expDir.find('experiments'):]
            if expPath[-1] == '/':
                expPath = expPath[:-1]
            madNotify = MadrigalNotify(self.__madDB)
            message = 'You requested to be notified when the experiment: %s from the Madrigal site %s was updated. A new file %s has been added to that experiment at %s. '  \
                % (expPath, self.__madDB.getTopLevelUrl(), os.path.basename(madFilename), str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            message += 'Please contact %s if you wish to be unregistered.' % (self.__madDB.getContactEmail())
                
            # first deal with users registered for just this experiment
            userList = self._userData.getRegisteredUsers(expPath)
            if len(userList) > 0:
                for user in userList:
                    try:
                        madNotify.notify(user, message, 'Update to Madrigal experiment you registered interest in')
                    except:
                        print(('Warning - email to %s failed to be sent' % (user)))
                        
            # next deal with users registered for instrument in general
            madExpObj = madrigal.metadata.MadrigalExperiment(self.__madDB, os.path.join(expDir, 'expTab.txt'))
            kinst = madExpObj.getKinstByPosition(0)
            userList = self._userData.getRegisteredInstUsers(kinst)
            if len(userList) > 0:
                for user in userList:
                    try:
                        madNotify.notify(user, message, 'Update to Madrigal instrument data you registered interest in')
                    except:
                        print(('Warning - email to %s failed to be sent' % (user)))
            



    def changeFileStatus(self,
                         expDir,
                         filename,
                         category = None,
                         fileDesc = None,
                         permission = None,
                         kindat = None,
                         fileAnalyst = None,
                         fileAnalystEmail = None):
        """changeFileStatus is used to change category, fileDesc, or permission of a register file in fileTab.txt.

        Inputs:

            expDir - full path to experiment directory 
        
            filename - basename of existing Madrigal file already registered in fileTab.txt
            
            permission - 0 (public) or 1 (private). If None (default), leave unchanged. 
            
            fileDesc - file description. If None (default), leave unchanged.

            category - 1=default, 2=variant, or 3=history. If None (default), leave unchanged.

            kindat - kindat (int). If None (default), leave unchanged.
            
            fileAnalyst - name of file analyst.  If None (default), leave unchanged.
            
            fileAnalystEmail - email of file analyst.  If None (default), leave unchanged.
        """
        try:
            fileTabInfo = madrigal.metadata.MadrigalMetaFile(self.__madDB, os.path.join(expDir, 'fileTab.txt'))
        except:
            raise ValueError('Unable to open fileTab.txt in %s' % (expDir))

        # be sure filename is basename
        filename = os.path.basename(filename)

        # search all Madrigal files in fileTab.txt for right file
        found = False
        fileCount = fileTabInfo.getFileCount()

        for index in range(fileCount):
            thisFilename = fileTabInfo.getFilenameByPosition(index)
            if thisFilename == filename:
                found = True
                if category != None:
                    fileTabInfo.setCategoryByPosition(index, category)
                if fileDesc != None:
                    fileTabInfo.setStatusByPosition(index, fileDesc)
                if permission != None:
                    fileTabInfo.setAccessByPosition(index, permission)
                if kindat != None:
                    fileTabInfo.setKindatByPosition(index, kindat)
                if fileAnalyst != None:
                    fileTabInfo.setAnalystByPosition(index, fileAnalyst)
                if fileAnalystEmail != None:
                    fileTabInfo.setAnalystEmailByPosition(index, fileAnalystEmail)
                fileTabInfo.writeMetadata()
                break

        if found == False:
            raise ValueError('Madrigal file %s not found in %s' % (filename, os.path.join(expDir, 'fileTab.txt')))


    def overwriteMadrigalFile(self,
                              expDir,
                              madFilename,
                              notify = True):
        """overwriteMadrigalFile overwrites a file already registered in fileTab.txt.

        Automatically updates expTab.txt with any start or end experiment times.

        Inputs:

            expDir - full path to experiment directory
        
            madFilename - full path to the new Madrigal file.  Basename must match that of one in fileTab.txt.
            
            notify - if True (the default), send a message to all registered users.  If False, do not.
    

        Returns: None

        Affects: Overwrites existing Madrigal file.  May modify expTab.txt with new start/end times.
        Also updated any cached files.
        """
        # verify this file registered
        try:
            fileTabInfo = madrigal.metadata.MadrigalMetaFile(self.__madDB, os.path.join(expDir, 'fileTab.txt'))
        except:
            raise ValueError('Unable to open fileTab.txt in %s' % (expDir))

        # get basename
        filename = os.path.basename(madFilename)

        # search all Madrigal files in fileTab.txt for right file
        found = False
        fileCount = fileTabInfo.getFileCount()

        for index in range(fileCount):
            thisFilename = fileTabInfo.getFilenameByPosition(index)
            if thisFilename == filename:
                found = True
                break

        if found == False:
            raise ValueError('%s not found in %s' % (filename, os.path.join(expDir, 'fileTab.txt')))

        # cp madFilename to new directory
        shutil.copy(madFilename, os.path.join(expDir, filename))
        os.chmod(os.path.join(expDir, filename), 0o664)

        # rm and re-populate overview
        os.remove(os.path.join(expDir, 'overview', filename + '.summary'))
        fileInfo = madrigal.data.MadrigalFile(os.path.join(expDir, filename), self.__madDB)
        
        cachedName = os.path.join(expDir, 'overview', filename + '.txt')
        if os.access(cachedName + '.gz', os.R_OK):
            os.remove(cachedName + '.gz')
            madrigal.cedar.convertToText(os.path.join(expDir, filename), cachedName)
            subprocess.check_call(['gzip', cachedName])
            
        cachedName = os.path.join(expDir, 'overview', filename + '.nc')
        if os.access(cachedName, os.R_OK):
            os.remove(cachedName)
            madrigal.cedar.convertToNetCDF4(os.path.join(expDir, filename), cachedName)

        # update expTab.txt against all registered files
        self.updateExpTab(expDir)
        
        if notify:
            # get expPath without MAD ROOT
            expPath = expDir[expDir.find('experiments'):]
            if expPath[-1] == '/':
                expPath = expPath[:-1]
            madNotify = MadrigalNotify(self.__madDB)
            message = 'You requested to be notified when the experiment: %s from the Madrigal site %s was updated. The file %s has been modified in that experiment at %s.'  \
                % (expPath, self.__madDB.getTopLevelUrl(), os.path.basename(madFilename), str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            message += 'Please contact %s if you wish to be unregistered.' % (self.__madDB.getContactEmail())
            
            userList = self._userData.getRegisteredUsers(expPath)
            if len(userList) > 0:
                for user in userList:
                    try:
                        madNotify.notify(user, message, 'Update to Madrigal experiment you registered interest in')
                    except:
                        print(('Warning - email to %s failed to be sent' % (user)))
                        
            # next deal with users registered for instrument in general
            madExpObj = madrigal.metadata.MadrigalExperiment(self.__madDB, os.path.join(expDir, 'expTab.txt'))
            kinst = madExpObj.getKinstByPosition(0)
            userList = self._userData.getRegisteredInstUsers(kinst)
            if len(userList) > 0:
                for user in userList:
                    try:
                        madNotify.notify(user, message, 'Update to Madrigal instrument data you registered interest in')
                    except:
                        print(('Warning - email to %s failed to be sent' % (user)))



    def removeMadrigalFile(self,
                           expDir,
                           madFilename,
                           allowMissing=False):
        """removeMadrigalFile removes a file already registered in fileTab.txt.

        Automatically updates expTab.txt with any start or end experiment times.

        Inputs:

            expDir - full path to experiment directory
        
            madFilename - Name of Madrigal file to be removed.  Basename must match that of one in fileTab.txt.
            
            allowMissing - if True, remove file successfully even if the file cannot be removed from expDir. If False,
                the default, raise an error if file does not exist.

        Returns: None

        Affects: Removes existing Madrigal file and removes its line from fileTab.txt.  May modify expTab.txt
        with new start/end times
        """
        # verify this file registered
        try:
            fileTabInfo = madrigal.metadata.MadrigalMetaFile(self.__madDB, os.path.join(expDir, 'fileTab.txt'))
        except:
            raise ValueError('Unable to open fileTab.txt in %s' % (expDir))

        # get basename
        filename = os.path.basename(madFilename)

        # delete line from fileTab.txt
        fileTabInfo.deleteRowByFilename(filename)

        # write new version
        fileTabInfo.writeMetadata()
        
        # state variable to detect deletion of missing file
        was_missing = False

        # rm filename and overview data
        try:
            os.remove(os.path.join(expDir, filename))
        except:
            if allowMissing:
                print(('Warning: Unable to remove %s' % (os.path.join(expDir, filename))))
                was_missing = True
            else:
                raise
        try:
            os.remove(os.path.join(expDir, 'overview', filename + '.summary'))
        except:
            pass
        
        # sometimes conversion to Madrigal 3 left a copy in overview - remove this too if its there
        try:
            os.remove(os.path.join(expDir, 'overview', filename))
        except:
            pass
        
        
        cachedName = os.path.join(expDir, 'overview', filename + '.txt')
        if os.access(cachedName + '.gz', os.R_OK):
            os.remove(cachedName + '.gz')
            
        cachedName = os.path.join(expDir, 'overview', filename + '.nc')
        if os.access(cachedName, os.R_OK):
            os.remove(cachedName)

        # update expTab.txt against all registered files
        if not was_missing:
            self.updateExpTab(expDir)
        
        



    def addWebFile(self,
                   expDir,
                   source,
                   relativePath):
        """addWebFile writes a non-Madrigal file meant to be displayed on the web to somewhere within a Madrigal experiment directory.

            All needed directories will be created if needed.

            Inputs:

                expDir - full path to experiment directory

                source - local web file to write to Madrigal

                relativePath - path relative to expDir to write source file to.  If relativePath ends
                with /, then basename from source used.  Otherwise, basename from relativePath used.

            Returns: None

            Affects: writes a non-Madrigal file to expDir on Madrigal
        """
        # verify expDir is a real Madrigal experiment directory
        try:
            fileTabInfo = madrigal.metadata.MadrigalMetaFile(self.__madDB, os.path.join(expDir, 'fileTab.txt'))
        except:
            raise ValueError('%s not a valid experiment directory - no fileTab.txt' % (expDir))

        if not os.access(os.path.join(expDir, os.path.dirname(relativePath)), os.R_OK):
            # make all dirs
            os.umask(0000)
            os.makedirs(os.path.join(expDir, os.path.dirname(relativePath)), 0o777)
            
        if os.path.basename(relativePath) == '':
            shutil.copy(source, os.path.join(expDir, relativePath, os.path.basename(source)))
            os.chmod(os.path.join(expDir, os.path.dirname(relativePath), os.path.basename(source)), 0o664)
        else:
            shutil.copy(source, os.path.join(expDir, relativePath))
            os.chmod(os.path.join(expDir, relativePath), 0o664)

        

    def updateExpTab(self, expDir):
        """updateExpTab rewrites expTab.txt based on all the Madrigal files registered in fileTab.txt.

        Inputs:

            expDir - full path to experiment directory

        Returns: None

        Affects: rewrites expTab.txt in expDir based on all the Madrigal files registered in fileTab.txt.
        """
        try:
            fileTabInfo = madrigal.metadata.MadrigalMetaFile(self.__madDB, os.path.join(expDir, 'fileTab.txt'))
        except:
            raise ValueError('Unable to open fileTab.txt in %s' % (expDir))

        try:
            expInfo = madrigal.metadata.MadrigalExperiment(self.__madDB, os.path.join(expDir, 'expTab.txt'))
        except:
            raise ValueError('Unable to open expTab.txt in %s' % (expDir))

        # we only need to modify start and end times of experiment
        startTime = None
        endTime = None
        # we'd perfer to use default times if possible
        startTimeDefault = None
        endTimeDefault = None

        # search all Madrigal files for earliest time, latest time
        fileCount = fileTabInfo.getFileCount()
        if fileCount == 0:
            return

        for index in range(fileCount):
            thisMadfilename = fileTabInfo.getFilenameByPosition(index)
            thisCategory = fileTabInfo.getCategoryByPosition(index)
            try:
                fileInfo = madrigal.data.MadrigalFile(os.path.join(expDir, thisMadfilename))
            except:
                print('WARNING: Problem with expDir=%s and thisMadfilename=%s' % (expDir, thisMadfilename))
                continue
            thisStartTimeList = fileInfo.getEarliestTime()
            thisStartTime = datetime.datetime(thisStartTimeList[0],
                                              thisStartTimeList[1],
                                              thisStartTimeList[2],
                                              thisStartTimeList[3],
                                              thisStartTimeList[4],
                                              thisStartTimeList[5])
            thisEndTimeList = fileInfo.getLatestTime()
            thisEndTime = datetime.datetime(thisEndTimeList[0],
                                            thisEndTimeList[1],
                                            thisEndTimeList[2],
                                            thisEndTimeList[3],
                                            thisEndTimeList[4],
                                            thisEndTimeList[5])

            if startTime == None:
                startTime = thisStartTime
            else:
                if startTime > thisStartTime:
                    startTime = thisStartTime

            if endTime == None:
                endTime = thisEndTime
            else:
                if endTime < thisEndTime:
                    endTime = thisEndTime
                    
            if thisCategory == 1:
                if startTimeDefault == None:
                    startTimeDefault = thisStartTime
                else:
                    if startTimeDefault > thisStartTime:
                        startTimeDefault = thisStartTime
    
                if endTimeDefault == None:
                    endTimeDefault = thisEndTime
                else:
                    if endTimeDefault < thisEndTime:
                        endTimeDefault = thisEndTime

        # modify expTab.txt and write
        if startTimeDefault:
            expInfo.setExpStartDateTimeByPosition(startTimeDefault)
        else:
            expInfo.setExpStartDateTimeByPosition(startTime)
        if endTimeDefault:
            expInfo.setExpEndDateTimeByPosition(endTimeDefault)
        else:
            expInfo.setExpEndDateTimeByPosition(endTime)
        expInfo.writeMetadata()


    def updateMaster(self, skipGeo=False):
        """updateMaster is a method to update the local metadata.

        Replaces the former tcl script.

        Gathers data from experiment directories into metadata/expTab.txt and metadata/fileTab.txt.
        Also gathers metadata from OpenMadrigal to update metadata/expTabAll.txt and metadata/fileAllTab.txt,
        to update high level metadata siteTab.txt, instTab.txt, instType.txt, madCatTab.txt, parcods.tab.
        Also updates geophysical data.
        """
        binDir = os.path.join(self.__madDB.getMadroot(), 'bin')

        # update geophysical data
        if not skipGeo:
            print('*** Checking for any geophysical file updates ***')
            cmd = os.path.join(binDir, 'checkGeoUpdate.py')
            os.system(cmd)
        else:
            print('Warning - skipping updating geophysical files too often will make them out of date.')
        
        print('*** Updating local metadata ***')
        self.__updateLocalMetadata__()
        print('*** Updating metadata from other Madrigal sites ***')
        self.__updateGlobalMetadata__()
        #print('*** Checking OpenMadrigal for any metadata updates ***')
        #self.__checkOpenMadrigalMetadata__()

        # instParmTab.txt
        print('*** Rebuilding instParmTab.txt ***')
        obj = madrigal.metadata.MadrigalInstrumentParameters(self.__madDB)
        obj.rebuildInstParmTable()
        
        # instKindatTab.txt
        print('*** Rebuilding instKindatTab.txt ***')
        obj = madrigal.metadata.MadrigalInstrumentKindats(self.__madDB)
        obj.rebuildInstKindatTable()

        print('updateMaster complete...')



    def __updateLocalMetadata__(self):
        """__updateLocalMetadata__ is a private method to update metadata/expTab.txt and metadata/fileTab.txt
        from the local metadata in the experiments[0-9]* directory
        """
        localSiteID = self.__madDB.getSiteID() # used to check that experiments do not have wrong siteID
        
        metaDict = {}
        metaDict['expText'] = [] # a list of text lines of combined expTab.txt file
        metaDict['expIds'] = [] # a list of all expIds found in locals dirs
        metaDict['expIds2'] = [] # a list of all expIds found summary expDir.txt
        metaDict['fileText'] = [] # a list of text lines of combined fileTab.txt file
        metaDict['presentCount'] = 0 # experiment count so far
        metaDict['totalCount'] = 0 # count of all experiments found in first count
        metaDict['localSiteId'] = localSiteID
        
        # make sure metaDict['expIds'] and metaDict['expIds2'] contains minimum value
        metaDict['expIds'].append(self.__madDB.getSiteID() * 10000000)
        metaDict['expIds2'].append(self.__madDB.getSiteID() * 10000000)
        
        # get all experiment directories
        expDirList = self.__madDB.getExperimentDirs()
        
        # first walk to to simply fill out metaDict['expIds']
        for thisExpDir in expDirList:
            if not os.path.isdir(thisExpDir):
                continue
            for root, dirs, files, in os.walk(thisExpDir):
                         self.__walkExpDirIds__(metaDict, root, dirs + files)
        
        for thisExpDir in expDirList:
            if not os.path.isdir(thisExpDir):
                continue
            for root, dirs, files in os.walk(thisExpDir):
                         self.__walkExpDir__(metaDict, root, dirs + files)

        # create backup of expTab
        ret = os.system(f"mv {os.path.join(self.__madDB.getMadroot(), 'metadata/expTab.txt')} {os.path.join(self.__madDB.getMadroot(), 'metadata/expTab_backup.txt')}")
        if ret != 0:
            print("Problem creating backup expTab")

        # update expTab.txt
        f = open(os.path.join(self.__madDB.getMadroot(), 'metadata/expTab.txt'), 'w', encoding='utf-8')
        delimiter = ''
        f.write(delimiter.join(metaDict['expText']))
        f.close()
        
        # now sort it by date to speed searches
        madExpObj = madrigal.metadata.MadrigalExperiment(self.__madDB)
        madExpObj.sortByDateSite()
        madExpObj.writeMetadata(os.path.join(self.__madDB.getMadroot(), 'metadata/expTab.txt'))

        # create backup of fileTab
        ret = os.system(f"mv {os.path.join(self.__madDB.getMadroot(), 'metadata/fileTab.txt')} {os.path.join(self.__madDB.getMadroot(), 'metadata/fileTab_backup.txt')}")
        if ret != 0:
            print("Problem creating backup fileTab")

        # update fileTab.txt
        f = open(os.path.join(self.__madDB.getMadroot(), 'metadata/fileTab.txt'), 'w', encoding='utf-8')
        f.write(delimiter.join(metaDict['fileText']))
        f.close()


    def __updateGlobalMetadata__(self):
        """__updateGlobalMetadata__ is a private method to update metadata/expTabAll.txt and metadata/fileTabAll.txt
        from the main madrigal server.
        """

        expTabAll = ''
        fileTabAll = ''

        localSiteID = self.__madDB.getSiteID()

        siteList = self.__madSite.getSiteList()

        for site in siteList:
            siteID = site[0]
            # skip local site
            if siteID == localSiteID:
                continue
            siteName = site[1]
            siteDir = '%s_%i' % (siteName, siteID)

            expMetadataFile = os.path.join(siteDir, 'expTab.txt')
            fileMetadataFile = os.path.join(siteDir, 'fileTab.txt')

            try:
                thisExpText  = self.__openMad.getMetadataFromOpenMadrigal(expMetadataFile)
                thisFileText = self.__openMad.getMetadataFromOpenMadrigal(fileMetadataFile)
            except:
                continue

            expTabAll += thisExpText
            fileTabAll += thisFileText

        # append local data
        f = open(os.path.join(self.__madDB.getMadroot(), 'metadata/expTab.txt'))
        expTabAll += f.read()
        f.close()

        f = open(os.path.join(self.__madDB.getMadroot(), 'metadata/fileTab.txt'))
        fileTabAll += f.read()
        f.close()

        # if expTabAll and fileTabAll already exist, create backups of them
        if os.access(os.path.join(self.__madDB.getMadroot(), 'metadata/expTabAll.txt'), os.R_OK):
            # create backup of expTabAll
            ret = os.system(f"mv {os.path.join(self.__madDB.getMadroot(), 'metadata/expTabAll.txt')} {os.path.join(self.__madDB.getMadroot(), 'metadata/expTabAll_backup.txt')}")
            if ret != 0:
                print("Problem creating backup expTabAll")
        if os.access(os.path.join(self.__madDB.getMadroot(), 'metadata/fileTabAll.txt'), os.R_OK):
            # create backup of fileTabAll
            ret = os.system(f"mv {os.path.join(self.__madDB.getMadroot(), 'metadata/fileTabAll.txt')} {os.path.join(self.__madDB.getMadroot(), 'metadata/fileTabAll_backup.txt')}")
            if ret != 0:
                print("Problem creating backup fileTabAll")

        # write *All.txt files
        f = open(os.path.join(self.__madDB.getMadroot(), 'metadata/expTabAll.txt'), 'w', encoding='utf-8')
        f.write(expTabAll)
        f.close()
        
        # now sort it by date to speed searches
        madExpObj = madrigal.metadata.MadrigalExperiment(self.__madDB,
                                                         os.path.join(self.__madDB.getMadroot(), 
                                                                      'metadata/expTabAll.txt'))
        madExpObj.sortByDateSite()
        madExpObj.writeMetadata(os.path.join(self.__madDB.getMadroot(), 'metadata/expTabAll.txt'))


        f = open(os.path.join(self.__madDB.getMadroot(), 'metadata/fileTabAll.txt'), 'w', encoding='utf-8')
        f.write(fileTabAll)
        f.close()
        
        # rewrite instData.txt
        self._updateInstData()


    def __checkOpenMadrigalMetadata__(self):
        """__checkOpenMadrigalMetadata__ is a method that check the openmadrigal site for any
        updates to the following metadata files:

            1. siteTab.txt - the list of all Madrigal installations
            2. instTab.txt - the list of all Madrigal instruments
            3. instType.txt - the list of all instrument categories

        If an update is available, and the existing metadata file is an old one, it will be updated.
        However, if the local Madrigal adminstrator edits one of these files, then the file will
        not be updated.  If you want to change these files, it is best to contact the OpenMadrigal
        development administrator (madrigal@haystack.mit.edu)
        """
        metadataFiles = ('metadata/siteTab.txt', 'metadata/instTab.txt', 'metadata/instType.txt')
        url = 'https://cedar.openmadrigal.org/compareToArchive.py?filePath=%s&fileTextMd5=%s'
        
        for metadataFile in metadataFiles:
            localMetadataFile = os.path.join(self.__madDB.getMadroot(), 'metadata', os.path.basename(metadataFile))
            archivePath = 'madroot/%s' % (metadataFile)
            
            f = open(localMetadataFile)
            text = f.read().encode('utf-8')
            f.close()
            textMd5 = hashlib.md5(text)
            md5Str = textMd5.hexdigest() # md5 checksum of local metadata file

            thisUrl = url % (archivePath, md5Str)

            f = urllib.request.urlopen(thisUrl, timeout=200)
            result = f.read().decode('utf-8')
            f.close()

            items = result.split() # first item is latest revision tag, second is matching revision tag
            if len(items) != 2:
                raise IOError('Problem with url %s' % (thisUrl))

            if items[0] != 'None' and items[0] == items[1]:
                # everything is up to date
                continue

            if items[0] == 'None':
                # failed to find this metadata file
                raise IOError('Problem with url %s' % (thisUrl))

            if items[1] == 'None':
                # this metadata file must have been locally editted, print warning
                print('Metadata file %s has been locally edited - contact the OpenMadrigal administrator at haystack-madrigal-admin@mit.edu to update central metadata' % (metadataFile))
                continue

            # this metadata file needs updating
            print('Downloading revised version of metadata file %s from OpenMadrigal' % (metadataFile))
            text = self.__openMad.getLatestSubversionVersion(os.path.join('madroot',metadataFile))
            f = open(localMetadataFile, 'w', encoding='utf-8')
            f.write(text)
            f.close()
            
    def _updateInstData(self):
        """_updateInstData updates the summary files instData.txt and instDataPriv.txt based on 
        latest version of expTabAll.txt
        
        instData.txt and instDataPriv.txt has three comma-delimited columns:
            1. siteId
            2. kinst of non-test experiments at that siteID (only if site has most data)
            3. space separated ordered list of years with data available
            
        instDataPriv.txt includes local private data, in addition to public.
        
        Note that a kinst will only listed at one site.  If there is local data, it will be listed as
        local.  If it listed at more than one non-local site, it will be listed at the one with more
        experiments.
        """
        summDict = {} # local dict with keys=siteID, value=dict with key=kinst, value = years with non-test data
        summDictPriv = {} # same as summDict, but includes local private data
        kinstDict = {} # local dict with keys = kinst, value = dict with key=siteID, value = number of
                       # experiments.  Used to print warning if inst at multiple sites and to decide which
                       # site to incliude
        madExpObj = madrigal.metadata.MadrigalExperiment(self.__madDB,
                                                         os.path.join(self.__madDB.getMadroot(),
                                                                      'metadata/expTabAll.txt'))
        
        archive_sites = set([8,10])
        localSiteID = self.__madDB.getSiteID()
        for i in range(madExpObj.getExpCount()):
            siteID = madExpObj.getExpSiteIdByPosition(i)
            security = madExpObj.getSecurityByPosition(i)
            url = madExpObj.getExpUrlByPosition(i)
            # skip test experiments
            if self.__madDB.isTestExperiment(url, siteID) and security == 0:
                continue
            # skip all non-local archived data
            if siteID != localSiteID and security in (2,3):
                continue
            kinst = madExpObj.getKinstByPosition(i)
            sDTList = madExpObj.getExpStartDateTimeByPosition(i)
            eDTList = madExpObj.getExpEndDateTimeByPosition(i)
            # create a year list
            yearList = list(range(sDTList[0], eDTList[0]+1))
            # add to summDictPriv if not already there
            if siteID not in summDictPriv:
                summDictPriv[siteID] = {}
            if kinst not in summDictPriv[siteID]:
                summDictPriv[siteID][kinst] = [] # empty list of years
            for thisYear in yearList:
                if thisYear not in summDictPriv[siteID][kinst]:
                    summDictPriv[siteID][kinst].append(thisYear)
            # add to summDict if not already there and not private
            if security in (0,2):
                if siteID not in summDict:
                    summDict[siteID] = {}
                if kinst not in summDict[siteID]:
                    summDict[siteID][kinst] = [] # empty list of years
                for thisYear in yearList:
                    if thisYear not in summDict[siteID][kinst]:
                        summDict[siteID][kinst].append(thisYear)
            # add to kinstDict
            if kinst not in kinstDict:
                kinstDict[kinst] = {}
            if siteID not in list(kinstDict[kinst].keys()):
                kinstDict[kinst][siteID] = 1
                kinstSet = set(kinstDict[kinst].keys())
                if len(kinstSet.difference(archive_sites)) > 1:
                    print(('Note: kinst %i found at multiple non-archive sites: %s' % (kinst, str(kinstSet.difference(archive_sites)))))
            else:
                kinstDict[kinst][siteID] += 1
                
        # write to output files
        delimiter = ' '
        outputNames = ('instData.txt', 'instDataPriv.txt')
        dictList = (summDict, summDictPriv)
        for i in range(len(outputNames)):
            f = open(os.path.join(self.__madDB.getMadroot(), 'metadata', outputNames[i]), 'w', encoding='utf-8')
            thisDict = dictList[i]
            siteIDKeys = list(thisDict.keys())
            siteIDKeys.sort()
            for siteID in siteIDKeys:
                kinstKeys = list(thisDict[siteID].keys())
                kinstKeys.sort()
                for kinst in kinstKeys:
                    
                    # verify this kinst/siteID combination is the desired one
                    if localSiteID != siteID: 
                        if localSiteID in list(kinstDict[kinst].keys()):
                            continue # this is not local site, but local site has data and local site always wins
                        if len(kinstDict[kinst]) > 1:
                            accept = True # test whether this non-local site has the most experiments
                            thisCount = kinstDict[kinst][siteID]
                            for thisKey in list(kinstDict[kinst].keys()):
                                if kinstDict[kinst][thisKey] > thisCount:
                                    accept = False
                                    break
                            if not accept:
                                continue
                            
                    # this data is accepted - write it out
                    yearsList = thisDict[siteID][kinst]
                    yearsList.sort()
                    yearsStrList = [str(year) for year in yearsList]
                    yearsStr = delimiter.join(yearsStrList)
                    f.write('%i,%i,%s\n' % (siteID, kinst, yearsStr))
                    
            f.close()
        
                

    def __walkExpDir__(self, arg, dirname, names):
        """__walkExpDir__ is a private method called by os.walk.  arg is a dict with keys:
        1. extText = text of combined expTab.txt to be appended to
        2. fileText = text of combined fileTab.txt to be appended to
        3. presentCount = total experiments done so far
        4. localSiteId = local site id (int)
        5. expIds =  a list of all expIds found in locals dirs - set earlier
        6. expIds2 = a list of all expIds used so far in summary expDir.txt
        
        Sets values in arg
        """
        if 'expTab.txt' not in names:
            return

        # defines allowed experiment directory names
        dirConvStr1 = '/experiments[0-9]*/[0-9][0-9][0-9][0-9]/[a-z][a-z0-9][a-z0-9]/[^/]*'

        # check that dirname follows rule experiments[0-9]*/YYYY/sss/*
        madroot = self.__madDB.getMadroot()
        if madroot[-1] == '/':
            madroot = madroot[:-1]
        startIndex = len(madroot)
        testDir = dirname[startIndex:]
        if re.match(dirConvStr1, testDir) == None:
            return
        
        # make sure we only descend four levels
        count = 0
        items = testDir.split('/')
        for item in items:
            if len(item) > 0:
                count += 1
        if count != 4:
            return
        try:
            
            expObj = madrigal.metadata.MadrigalExperiment(self.__madDB,
                                                          os.path.join(dirname, 'expTab.txt'))
    
            # skip it if security == -1 (ignore flag)
            if expObj.getSecurityByPosition(0) == -1:
                return
    
            # skip if wrong site id
            if expObj.getExpSiteIdByPosition(0) != arg['localSiteId']:
                print('Warning: Experiment %s has wrong site id = %s.  This site id = %s' % \
                      (dirname, str(expObj.getExpSiteIdByPosition(0)), str(arg['localSiteId'])))
                return
    
            # modify experiment id if needed
            thisExpId = expObj.getExpIdByPosition(0)
            isNewExpId = False
            if thisExpId <= self.__madDB.getSiteID() * 10000000 or thisExpId in arg['expIds2']:
                # find a new unique id
                maxId1 = numpy.max(numpy.array(arg['expIds']))
                maxId2 = numpy.max(numpy.array(arg['expIds2']))
                newExpId = int(max([maxId1,maxId2])) + 1
                    
                expObj.setExpIdByPosition(0, newExpId)
                arg['expText'].append(str(expObj))
                # sanity check
                if newExpId in arg['expIds2']:
                    raise ValueError('Duplicate id %i' % (newExpId))
                arg['expIds2'].append(newExpId)
                expObj.writeMetadata()
                isNewExpId = True
                
                print(('Updated metadata in %s' % (str(dirname))))
                
                
            elif thisExpId in arg['expIds2']:
                raise ValueError('found unexpected duplicate expId %i' % (thisExpId))
            
            else:
                # normal case - this id already set and not changing
                arg['expText'].append(str(expObj))
                # sanity check
                if thisExpId in arg['expIds2']:
                    raise ValueError('Duplicate id %i' % (thisExpId))
                arg['expIds2'].append(thisExpId)
            
            arg['presentCount'] += 1
    
            if 'fileTab.txt' not in names:
                print('Info: Experiment %s has no fileTab.txt' % (dirname))
                return
    
            fileObj = madrigal.metadata.MadrigalMetaFile(self.__madDB,
                                                         os.path.join(dirname, 'fileTab.txt'))
    
            # set expId for all files
            for i in range(fileObj.getFileCount()):
                if isNewExpId:
                    fileObj.setExpIdByPosition(i, newExpId)
                else:
                    fileObj.setExpIdByPosition(i, thisExpId)
                
    
            arg['fileText'].append(str(fileObj))
            
            if isNewExpId:
                fileObj.writeMetadata()
                
            if arg['presentCount'] % 1000 == 0:
                print(('Done %i out of %i exps' % (arg['presentCount'], arg['totalCount'])))
            
        except:
            print((' *** Exception encounted in experiment directory %s ***' % (dirname)))
            raise
        
        
    def __walkExpDirIds__(self, arg, dirname, names):
        """__walkExpDirIds__ is a private method called by os.walk.  arg is a dict with keys:
        1. extText = text of combined expTab.txt to be appended to
        2. fileText = text of combined fileTab.txt to be appended to
        3. presentCount = total experiments done so far
        4. localSiteId = local site id (int)
        5. expIds =  a list of all expIds found in locals dirs - to be set here
        6. expIds2 = a list of all expIds used so far in summary expDir.txt
        
        Sets values in arg
        """
        if 'expTab.txt' not in names:
            return

        # defines allowed experiment directory names
        dirConvStr1 = '/experiments[0-9]*/[0-9][0-9][0-9][0-9]/[a-z][a-z0-9][a-z0-9]/[^/]*'

        # check that dirname follows rule experiments[0-9]*/YYYY/sss/*
        madroot = self.__madDB.getMadroot()
        if madroot[-1] == '/':
            madroot = madroot[:-1]
        startIndex = len(madroot)
        testDir = dirname[startIndex:]
        if re.match(dirConvStr1, testDir) == None:
            return
        
        # make sure we only descend four levels
        count = 0
        items = testDir.split('/')
        for item in items:
            if len(item) > 0:
                count += 1
        if count != 4:
            return
        try:
            
            expObj = madrigal.metadata.MadrigalExperiment(self.__madDB,
                                                          os.path.join(dirname, 'expTab.txt'))
    
            # skip it if security == -1 (ignore flag)
            if expObj.getSecurityByPosition(0) == -1:
                return
    
            # skip if wrong site id
            if expObj.getExpSiteIdByPosition(0) != arg['localSiteId']:
                print('Warning: Experiment %s has wrong site id = %i.  This site id = %s' % \
                      (dirname, expObj.getExpSiteIdByPosition(0), str(arg['localSiteId'])))
                return
    
            # add this id if unique
            thisExpId = expObj.getExpIdByPosition(0)
            if int(thisExpId) not in arg['expIds']:
                arg['expIds'].append(int(thisExpId))
                
            # increment totalCount
            arg['totalCount'] += 1
            
        except:
            print((' *** Exception encounted in experiment directory %s ***' % (dirname)))
            raise

        
        
        

class MadrigalNotify:
    """MadrigalNotify is an object used to send messages to an administrator about a Madrigal database.

    This object provides functions needed to send messages to an administrator about a Madrigal database, for now
    only sendAlert, which sends an email to the site administrator found is siteTab.txt (or if not
    possible, the admin in madrigal.cfg, and finally if all else fails, to root).

    Usage example:

        import madrigal.admin
    
        try:
        
            adminObj =  madrigal.admin.MadrigalNotify()
            adminObj.sendAlert('This is important!', 'Important Message')
            
        except madrigal.admin.MadrigalError, e:
        
            print e.getExceptionStr()


    Non-standard Python modules used:
    None

    Exceptions thrown: None - Note that MadrigalNotify tries every trick it knows to avoid
    throwing exceptions, since this is the class that will generally be called when there is a problem.

    Change history:

    Written by "Bill Rideout":mailto:wrideout@haystack.mit.edu  Dec. 4, 2001
    """
    

    #constants
    __defaultUser  = "root"
    """ Sets the default user to email to when all else fails. """

    __defaultServer  = "localhost"
    """ Sets the default server to send mail when all else fails. """


    def __init__(self, madDB = None):
        """__init__ initializes MadrigalNotify by getting some basic information from MadrigalDB and MadrigalSite.

        Note that MadrigalNotify tries every trick it knows to avoid throwing exceptions, since
        this is the class that will generally be called when there is a problem.

        Inputs: Existing MadrigalDB object, by default = None.
        
        Returns: void

        Affects: Initializes self.__binDir.

        Exceptions: None.
        """

        # get metadata dir
        if madDB == None:
            try:
                thisMadDB = madrigal.metadata.MadrigalDB()
            except:
                # note that the main configuration file is unavailable 
                # the best that can be done is send an email to root using localhost mailserver
                self.__emailAddress = self.__defaultUser
                self.__emailServer  = self.__defaultServer
                thisMadDB = None
        else:
            thisMadDB = madDB
        self.madDB = thisMadDB

        if thisMadDB != None:
            self.__emailServer  = thisMadDB.getMailserver()
            # now try to get email from site metadata, if failure, use config contact info
            try:
                thisSite = madrigal.metadata.MadrigalSite()
                self.__emailAddress = thisSite.getSiteEmail(thisMadDB.getSiteID())
                if self.__emailAddress == None:
                    # couldn't read metadata - use madrigal.cfg
                    self.__emailAddress = thisMadDB.getContactEmail()
            except:
                # couldn't read metadata - use madrigal.cfg
                self.__emailAddress = thisMadDB.getContactEmail()

            #make sure madrigal.cfg worked - if not use root
            if self.__emailAddress == None:
                self.__emailAddress = self.__defaultUser


    def sendAlert(self, message, subject = None):
        """sendAlert sends an email with the given message and optional title.

        Inputs: message (string), and optional title (string)
        
        Returns: void

        Affects: none

        Exceptions: None.
        """
        
        msg = email.message.EmailMessage()
        msg.set_content(message)
            
        # set up message
        msg['Subject'] = str(subject)
        msg['From'] = self.__emailAddress
        msg['To'] = self.__emailAddress
    
        with smtplib.SMTP(self.__emailServer) as s:
            s.send_message(msg)

        
        
    def notify(self, emailAddress, message, subject):
        """notify sends an email with the given message and title to email.

        Inputs: emailAddress (string), message (string), and subject (string)
        
        Returns: void

        Affects: none

        Exceptions: None.
        """
        
        msg = email.message.EmailMessage()
        msg.set_content(message)
            
        # set up message
        msg['Subject'] = str(subject)
        msg['From'] = self.__emailAddress
        msg['To'] = emailAddress
    
        with smtplib.SMTP(self.__emailServer) as s:
            s.send_message(msg)



class MadrigalError(Exception):
    """MadrigalError is an exception class that is thrown for all known errors in using Madrigal Py lib.

    Usage example:

        import sys, traceback
        import madrigal.admin
    
        try:
        
            test = open('ImportantFile.txt', 'r')
            
        except:
        
            raise madrigal.admin.MadrigalError('ImportantFile.txt not opened!',
                                                traceback.format_exception(sys.exc_info()[0],
                                                                        sys.exc_info()[1],
                                                                        sys.exc_info()[2]))
    """


    def __init__(self, strInterpretation, exceptionList):
        """ __init__ gathers the interpretation string along with all information from sys.exc_info().

        Inputs: strIntepretation - A string representing the programmer's interpretation of
        why the exception occurred

                exceptionList - a list of strings completely describing the exception.
                Generated by traceback.format_exception(sys.exc_info()[0],
                                                        sys.exc_info()[1],
                                                        sys.exc_info()[2])
        
        Returns: Void.

        Affects: Initializes class member variables _strInterp, _strExcList.

        Exceptions: None.
        """
        
        self._strInterp = strInterpretation
        self._strExcList = exceptionList

        
    def getExceptionStr(self):
        """ getExceptionStr returns a formatted string ready for printing completely describing the exception.

        Inputs: None
        
        Returns: A formatted string ready for printing completely describing the exception.

        Affects: None

        Exceptions: None.
        """
        excStr = 'The following Madrigal Python exception has occurred:\n'
        excStr = excStr + self._strInterp + '\n\n'

        if self._strExcList != None:
            for item in self._strExcList:
                excStr = excStr + str(item) + '\n'

        return excStr
    
    def __str__(self):
        return(self.getExceptionStr())


    def getExceptionHtml(self):
        """ getExceptionHtml returns an Html formatted string completely describing the exception.

        Inputs: None
        
        Returns: A formatted string ready for printing completely describing the exception.

        Affects: None

        Exceptions: None.
        """
        
        excStr = '<BR>The following Madrigal Python exception has occurred:\n<BR>'
        excStr = excStr + self._strInterp + '\n<BR>\n'

        if self._strExcList != None:
            for item in self._strExcList:
                excStr = excStr + str(item) + '\n<BR>'

        return excStr

    

if __name__ == '__main__':

    test = MadrigalNotify()

    test.sendAlert('This is a message from the python module MadrigalNotify', 'Test from MadrigalNotify')

    print('Hopefully message sent - check.')


    test = MadrigalDBAdmin()

    """
    expDir = test.createRTExperiment(datetime.datetime.now(),
                           4,
                           32,
                           'Dummy experiment',
                           ('mlhrt1','mlhrt2'),
                           (30,30),
                           (0,0),
                           ('preliminary','very preliminary'))

    mlhrtFile = open('/home/hyperion/brideout/mlhrt1')
    mlhrt = mlhrtFile.read()
    mlhrtFile.close()
    
    
    test.appendRTMadrigalFile(expDir,
                            'mlhrt1',
                            mlhrt)

    # not real data, but shouldn't be checked
    test.appendRTMadrigalFile(expDir,
                            'mlhrt1',
                            'qqqqqqqqqqqqqqqqqqqqqqqq')

    mlhrtFile = open('/home/hyperion/brideout/mlhrt2')
    mlhrt = mlhrtFile.read()
    mlhrtFile.close()

    try:
        # this should raise a wrong file type exception
        test.appendRTMadrigalFile(expDir,
                                'mlhrt2',
                                mlhrt)
    except:
        traceback.print_exc()


    expDir = test.createMadrigalExperiment('/home/hyperion/brideout/mlh050429c.000',
                                        'Dummy experiment',
                                        0,
                                        'test exp',
                                        30,
                                        1)
    test.overwriteMadrigalFile(expDir,
                              '/home/hyperion/brideout/junk/mlh050429c.000')

    test.addWebFile(expDir,
                   '/home/hyperion/brideout/junk.html',
                   'html/second/')"""

    expDir = '/home/grail/brideout/madroot/experiments/1998/mlh/20jan98'

    try:
        test.addMadrigalFile(expDir,
                             '/tmp/mlh980120g.001',
                             0,
                             'second file')
    except:
        traceback.print_exc()
    """
    
    test.changeFileStatus(expDir,
                          '/home/hyperion/brideout/mlh050429c.000',
                          3,
                          'new status',
                          1)

    print 'about to run updateMaster'
    test.updateMaster(True)
    """
