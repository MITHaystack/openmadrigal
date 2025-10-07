"""web is the module that interfaces to cgi madrigal web pages.

The web module contains general functions to produce html, along with producing
html relating to specific user data or madrigal data.
"""

# $Id: web.py 7638 2024-04-29 14:27:57Z brideout $

import time, os
import os.path
import calendar
import fnmatch
import datetime
import types, traceback
import http.cookies
import urllib.request, urllib.parse, urllib.error
import glob
import calendar
import urllib.parse
import math
import random
import tempfile
import subprocess
import tarfile
import shutil
import re

# third party imports
import numpy
import django.urls

import madrigal.metadata
import madrigal.derivation
import madrigal.data
import madrigal.isprint
import madrigal.ui.userData
import madrigal.admin

class MadrigalWeb:
    """MadrigalWeb is the class that produces output for the web.

    All text written to the web is produced in this class.

    Non-standard Python modules used:
    None

    Change history:

    Written by "Bill Rideout":mailto:wrideout@haystack.mit.edu  Dec. 17, 2001
    """
    

    _MaxSleep     = 10

    def __init__(self, madDB = None, request = None):
        """__init__ initializes MadrigalWeb by reading from MadridalDB..

        Inputs: 
        
            madDB:  MadrigalDB object, by default = None.
            request: django request object.  By default None
        
        Returns: void

        Affects: Initializes self._metaDir, self._logFile.

        Exceptions: None.
        """

        if madDB == None:
            self._madDB = madrigal.metadata.MadrigalDB()
        else:
            self._madDB = madDB
            
        self._request = request

        self._binDir = self._madDB.getBinDir()
        self._instObj = madrigal.metadata.MadrigalInstrument(self._madDB)
        self._madKindatObj = madrigal.metadata.MadrigalKindat(self._madDB)

        metaDir = self._madDB.getMetadataDir()

        # get todays year
        now = datetime.datetime.now()

        thisYear = '%04i' % (now.year)

        self._logFile = os.path.join(metaDir, 'userdata', 'access_%s.log' % (thisYear))

        # be sure it exists
        if not os.access(self._logFile, os.R_OK):
            f=open(self._logFile, 'w')
            f.close()

        # keep track of whether user trusted
        self._isTrusted_ = None
        
        # cache Madrigal objects as needed to imprive performance
        self._madExpObjExpID = None # will be set to a MadrigalExperiment object sorted by expId when first needed
        self._madExpObjDate = None # will be set to a MadrigalExperiment object sorted by date when first needed




    def getRulesOfTheRoad(self, PI=None, PIEmail=None):
        """ getRulesOfTheRoad returns a string giving the rules in html formal for using madrigal data.

        Inputs: PI - contact name. Default is site name.
            PIEmail - email link.  Default is site admin.
        
        Returns: a string giving the rules in html formal for using madrigal data

        Affects: None.

        Exceptions: None.
        """
        if not PI or not PIEmail:
            # get the site name
            siteObj = madrigal.metadata.MadrigalSite(self._madDB)
            siteID = self._madDB.getSiteID()
            contactName = str(siteObj.getSiteName(siteID))
            contactEmail = str(siteObj.getSiteEmail(siteID))
        else:
            contactName = str(PI)
            contactEmail = str(PIEmail)
        
        returnStr = 'Please contact %s at ' % (contactName)

        returnStr = returnStr + '<a href="mailto:' + contactEmail + '">' + \
                    contactEmail + '</a> before using this data in a report or publication.'

        return returnStr
    
        
    def generateLogout(self, fileName, expName):
        """ generateLogout generates a java script which sends a user to the madLogin page to logout automatically.

        Inputs: fileName: the madrigal file to return to
                expName:  the experiment name of the file to return to
        
        Returns: a java script which sends a user to the madLogin page to logout automatically

        Affects: None.

        Exceptions: None.
        """

        print('<script language = "JavaScript">')
        print('\twindow.location = "madLogin?fileName=' + \
              fileName + '&expName=' + \
              expName + '&state=autoLogout"')
        print('</script>')


    def isTrusted(self):
        """ isTrusted returns 1 if browser ip matches any in the trustedIPs.txt file; 0 otherwise.

        Inputs: None
        
        Returns: 1 if browser ip matches any in the trustedIPs.txt file; 0 otherwise.  Also returns
        0 if no browser ip available or trustedIPs.txt cannot be opened.

        Affects: None.

        Exceptions: None.
        """
        if not self._isTrusted_ is None:
            return(self._isTrusted_)
        
        if self._request is None:
            self._isTrusted_ = 0
            return 0
        
        try:
            trustFile = open(self._madDB.getMadroot() + '/trustedIPs.txt', 'r')
        except:
            return 0

        # try to read env var REMOTE_ADDR and HTTP_X_FORWARDED_FOR
        userIPList = []
        if self._request.META.get('REMOTE_ADDR')!= None:
            userIPList.append(self._request.META.get('REMOTE_ADDR'))
        if self._request.META.get('HTTP_X_FORWARDED_FOR') != None:
            ips = self._request.META.get('HTTP_X_FORWARDED_FOR').split(',')
            for ip in ips:
                userIPList.append(ip.strip())
        if len(userIPList) == 0:
            self._isTrusted_ = 0
            return 0
        if len(userIPList[0]) < 7:
            # ip address too short
            self._isTrusted_ = 0
            return 0

        # loop through trustedIPs.txt to find a match
        ipList = trustFile.readlines()
        for userIP in userIPList:
            for ipItem in ipList:
                # match using filename matching with *
                if fnmatch.fnmatch(userIP, ipItem.strip()):
                    self._isTrusted_ = 1
                    return 1

        # out of loop, no match found
        self._isTrusted_ = 0
        return 0


    def logDataAccess(self, fullFilenameList, user_fullname=None, user_email=None, user_affiliation=None):
        """ logDataAccess logs queries that access low-level data.

        Records user name, email, affiliation, datetime, and full path the file(s) accessed.

        Inputs:

            fullFilenameList either a list of full filenames, or a string with one filename

            user_fullname - if None, try to read from cookie.  Also, any commas replaced by spaces.

            user_email - if None, try to read from cookie.  Also, any commas replaced by spaces.

            user_affiliation - if None, try to read from cookie.  Also, any commas replaced by spaces.
            

        Outputs: None

        Affects: Write line to log file with 5 or more comma-delimited columns.  Example:

            Bill Rideout,brideout@haystack.mit.edu,MIT Haystack,2002-12-25 00:00:00, \
            /opt/madrigal/experiments/2005/mlh/01sep05/mlh050901g.001,/opt/madrigal/experiments/2005/mlh/02sep05/mlh050902g.001

        Uses _getLock and _dropLock to ensure single users access to log file
        """

        if user_fullname == None or user_email == None or user_affiliation == None:
        
            # try to get name, email, affiliation from cookie
            cookie = http.cookies.SimpleCookie()
            if 'HTTP_COOKIE' in os.environ:
                cookie.load(os.environ['HTTP_COOKIE'])
                try:
                    user_fullname = cookie["user_fullname"].value
                    user_email = cookie["user_email"].value
                    user_affiliation = cookie["user_affiliation"].value
                except:
                    # no way to write log
                    return

            if user_fullname == None or user_email == None or user_affiliation == None:
                return

        # strip out any commas
        user_fullname = user_fullname.replace(',', ' ')
        user_email = user_email.replace(',', ' ')
        user_affiliation = user_affiliation.replace(',', ' ')

        if type(fullFilenameList) in (list, tuple):
            delimiter = ','
            fileStr = delimiter.join(fullFilenameList)
        else:
            fileStr = str(fullFilenameList)
        

        now = datetime.datetime.now()


        nowStr = now.strftime('%Y-%m-%d %H-%M-%S')

        # lock out any method that writes to log file
        self._getLock(self._logFile)

        f = open(self._logFile, 'a')

        f.write('%s,%s,%s,%s,%s\n' % (user_fullname.encode('utf8'),
                                      user_email.encode('utf8'),
                                      user_affiliation.encode('utf8'),
                                      nowStr,
                                      fileStr))



        f.close()

        # done with log file - allow access to other writing calls
        self._dropLock(self._logFile)  
        
        
    def filterLog(self, tmpFile, kinstList=None, accessStartDate=None, accessEndDate=None):
        """filterLog writes a subsection of the access log to a temporary file
        
        Inputs:
        
            tmpFile - temporary file to write subsection of log to
            
            kinstList - list of kinsts to accept.  If None (the default), accept all instruments
            
            accessStartDate - if not None (the default), reject all access dates before
                datetime accessStartDate
                
            accessEndDate - if not None (the default), reject all access dates after
                datetime accessEndDate
            
        """
        f = open(tmpFile, 'w')
        
        accessLogs = glob.glob(os.path.join(self._madDB.getMadroot(), 'metadata/userdata/access_*.log'))
        accessLogs.sort()
        
        # addition for cedar only
        """accessLogs2 = glob.glob('/opt/cedar/metadata/userdata/access_*[0-9].log')
        accessLogs += accessLogs2
        accessLogs.sort()"""
        
        
        if kinstList:
            # create a dictionary of key = 3 letter inst mnem, value = kinstList
            instDict = {}
            instList = self._instObj.getInstrumentList()
            for inst in instList:
                if inst[1] in instDict:
                    instDict[inst[1]].append(inst[2])
                else:
                    instDict[inst[1]] = [inst[2]]
        
        for accessLog in accessLogs:
            # see if we can skip this year
            basename = os.path.basename(accessLog)
            try:
                year = int(basename[7:11])
            except:
                continue
            startYear = datetime.datetime(year,1,1,0,0,0)
            endYear = datetime.datetime(year,12,31,23,59,59)
            if accessStartDate:
                if accessStartDate > endYear:
                    continue
            if accessEndDate:
                if accessEndDate < startYear:
                    continue
            # this file can be huge, so read one line at a time
            fl = open(accessLog)
            while True:
                line = fl.readline()
                if len(line) == 0:
                    break
                items = line.strip().split(',')
                if len(items) != 5:
                    continue
                # walk through filters
                
                # kinst
                if kinstList:
                    # get the instrument mnemonic
                    dirs = items[-1].split('/')
                    if len(dirs) < 3:
                        continue
                    found = False
                    try:
                        for kinst in instDict[dirs[-3]]:
                            if kinst in kinstList:
                                found = True
                                break
                    except KeyError:
                        continue
                    if not found:
                        continue
                    
                # access time
                if accessStartDate or accessEndDate:
                    thisDT = datetime.datetime.strptime(items[-2], '%Y-%m-%d %H-%M-%S')
                    if accessStartDate:
                        if accessStartDate > thisDT:
                            continue
                    if accessEndDate:
                        if accessEndDate < thisDT:
                            continue
                        
                # all filters passed
                f.write(line)
                
            fl.close()
                
        f.close()
                
                    
                
        
    def createGlobalIsprintCmd(self, language, madrigalUrl, parmList, output,
                               user_fullname, user_email, user_affiliation,
                               start_datetime, end_datetime, instCode,
                               filterList, kindatList, expName, fileDesc,
                               seasonalStartDate, seasonalEndDate, format=None):
        """createGlobalIsprintCmd returns a string representing a global isprint command to run in a particular language.
        
        Inputs:
        
            language - which language to use.  Allowed values are ('python', 'Matlab', 'IDL')
            madrigalUrl - url to madrigal home page where data is
            parmList - ordered list of parameters requested.
            output - output file name
            user_fullname
            user_email
            user_affiliation
            start_datetime - a datetime object. Reject experiments before that datetime
            end_datetime - a datetime object. Reject experiments after that datetime
            instCode - instrument code (integer)
            filterList - a list of strings in form "mnem,lower,upper" where lower and/or upper may be empty
            kindatList - a list of kindat codes.  An empty list selects all kindats
            expName - filter experiments by the experiment name. Matching is case insensitive and fnmatch characters * and ? are allowed. 
                Empty string is no filtering by experiment name.
            fileDesc - filter files by the file description string. Matching is case insensitive and fnmatch characters * and ? are allowed. 
                Empty string is no filtering by file description.
            seasonalStartDate - a string in form 'MM/DD'.  Dates before then in any year will be ignored.  Assumes non-leap year.
                Empty string means no filtering by seasonal start date.
            seasonalEndDate - a string in form 'MM/DD'.  Dates after then in any year will be ignored.  Assumes non-leap year.
                Empty string means no filtering by seasonal end date.
            format - 'hdf5', 'ascii', or 'netCDF4'. If None, not specified (Madrigal 2 does not support this)
        """
        if language not in ('python', 'Matlab', 'IDL'):
            raise ValueError('language %s not supported' % (str(language)))
        
        # url
        if language == 'python':
            cmd = 'globalIsprint.py --verbose --url=%s ' % (madrigalUrl)
        elif language == 'Matlab':
            cmd = "globalIsprint('%s', ...\n " % (madrigalUrl)
        elif language == 'IDL':
            cmd = "madglobalprint, '%s',  $\n " % (madrigalUrl)
            
        # parms
        if len(parmList) == 0:
            raise ValueError('parmList cannot be empty')
        parmStr = ''
        for parm in parmList:
            parmStr += str(parm)
            if parm != parmList[-1]:
                parmStr += ','
        if language == 'python':
            cmd += '--parms=%s ' % (parmStr)
        elif language == 'Matlab':
            cmd += "'%s', ...\n " % (parmStr)
        elif language == 'IDL':
            cmd += "'%s',  $\n " % (parmStr)
            
        # output
        if language == 'python':
            cmd += '--output=%s ' % (output)
        elif language == 'Matlab':
            cmd += "'%s', ...\n " % (output)
        elif language == 'IDL':
            cmd += "'%s',  $\n " % (output)
            
        # user_fullname
        if language == 'python':
            cmd += '--user_fullname="%s" ' % (user_fullname)
        elif language == 'Matlab':
            cmd += "'%s', ...\n " % (user_fullname)
        elif language == 'IDL':
            cmd += "'%s',  $\n " % (user_fullname)
            
        # user_email
        if language == 'python':
            cmd += '--user_email=%s ' % (user_email)
        elif language == 'Matlab':
            cmd += "'%s', ...\n " % (user_email)
        elif language == 'IDL':
            cmd += "'%s',  $\n " % (user_email)
            
        # user_affiliation
        if language == 'python':
            cmd += '--user_affiliation="%s" ' % (user_affiliation)
        elif language == 'Matlab':
            cmd += "'%s', ...\n " % (user_affiliation)
        elif language == 'IDL':
            cmd += "'%s',  $\n " % (user_affiliation)
            
        
        # start_datetime
        if language == 'python':
            cmd += '--startDate="%s" ' % (start_datetime.strftime('%m/%d/%Y'))
        elif language == 'Matlab':
            cmd += "datenum('%s'), ...\n " % (start_datetime.strftime('%d-%b-%Y %H:%M:%S'))
        elif language == 'IDL':
            cmd += "julday(%i,%i,%i,%i,%i,%i),  $\n " % (start_datetime.month, start_datetime.day,
                                                          start_datetime.year, start_datetime.hour,
                                                          start_datetime.minute, start_datetime.second)
            
        # end_datetime
        if language == 'python':
            cmd += '--endDate="%s" ' % (end_datetime.strftime('%m/%d/%Y'))
        elif language == 'Matlab':
            cmd += "datenum('%s'), ...\n " % (end_datetime.strftime('%d-%b-%Y %H:%M:%S'))
        elif language == 'IDL':
            cmd += "julday(%i,%i,%i,%i,%i,%i),  $\n " % (end_datetime.month, end_datetime.day,
                                                          end_datetime.year, end_datetime.hour,
                                                          end_datetime.minute, end_datetime.second)
            
        # instrument
        if language == 'python':
            cmd += '--inst=%i ' % (instCode)
        elif language == 'Matlab':
            cmd += "%i, ...\n " % (instCode)
        elif language == 'IDL':
            cmd += "%i,  $\n " % (instCode)
            
        # format is here for Matlab or python
        if output == 'example.txt':
            format = None
        if language in ('Matlab', 'python'):
            if language == 'python':
                if not format is None:
                    if format.lower() == 'hdf5':
                        cmd += '--format=%s ' % ('Hdf5')
                    elif format in ('netCDF4', 'ascii'):
                        cmd += '--format=%s ' % (format)
            elif language == 'Matlab':
                if format is None:
                    cmd += "'', ...\n "
                elif format.lower() == 'hdf5':
                    cmd += "'%s', ...\n " % ('Hdf5')
                elif format in ('netCDF4', 'ascii'):
                    cmd += "'%s', ...\n " % (format)
            
        # filterList
        # add seasonal filters if needed 
        if len(seasonalStartDate) or len(seasonalEndDate):
            daynoFilterStr = self._getDaynoFilter(seasonalStartDate, seasonalEndDate)
            filterList.append(daynoFilterStr)
        if language == 'python':
            for filterItem in filterList:
                cmd += '--filter=%s ' % (filterItem)
        elif language == 'Matlab':
            filterStr = ''
            for filterItem in filterList:
                filterStr += 'filter=%s ' % (filterItem)
            cmd += "'%s', ...\n " % (filterStr)
        elif language == 'IDL':
            filterStr = ''
            for filterItem in filterList:
                filterStr += 'filter=%s ' % (filterItem)
            cmd += "'%s',  $\n " % (filterStr)
            
        # kindatList
        if language == 'python':
            if len(kindatList) == 0:
                pass
            else:
                kindatStr = '--kindat='
                for kindat in kindatList:
                    kindatStr += '%i' % (kindat)
                    if kindat != kindatList[-1]:
                        kindatStr += ','
                cmd += '%s ' % (kindatStr)
        elif language == 'Matlab':
            kindatStr = '['
            for kindat in kindatList:
                if kindat == 0:
                    continue
                kindatStr += '%i' % (kindat)
                if kindat != kindatList[-1]:
                    kindatStr += ','
            kindatStr += ']'
            cmd += "%s, ...\n " % (kindatStr)
        elif language == 'IDL':
            # make sure 0 not in list
            try:
                kindatList.remove(0)
            except ValueError:
                pass
            if len(kindatList) == 0:
                kindatStr = 'PTR_NEW()'
            else:
                kindatStr = '['
                for kindat in kindatList:
                    kindatStr += '%i' % (kindat)
                    if kindat != kindatList[-1]:
                        kindatStr += ','
                kindatStr += ']'
            cmd += "%s,  $\n " % (kindatStr)
            
        # expName
        if language == 'python':
            if len(expName) > 0:
                cmd += '--expName="%s" ' % (expName)
        elif language == 'Matlab':
            expName = expName.replace('*', '.*')
            expName = expName.replace('?', '.?')
            cmd += "'%s', ...\n " % (expName)
        elif language == 'IDL':
            cmd += "'%s',  $\n " % (expName)
            
        # fileDesc
        if language == 'python':
            if len(fileDesc) > 0:
                cmd += '--fileDesc="%s" ' % (fileDesc)
        elif language == 'Matlab':
            fileDesc = fileDesc.replace('*', '.*')
            fileDesc = fileDesc.replace('?', '.?')
            cmd += "'%s') " % (fileDesc)
        elif language == 'IDL':
            cmd += "'%s',  $\n "  % (fileDesc)
            
        # format is here for idl
        if language == 'IDL':
            if format is None:
                cmd += "'',  $\n "
            elif format.lower() == 'hdf5':
                cmd += "'hdf5',  $\n "
            elif format in ('netCDF4', 'ascii'):
                cmd += "'%s',  $\n "  % (format)
            
            
            
        return(cmd)
    
    
    
    def createGlobalDownloadCmd(self, language, madrigalUrl, output, format,
                               user_fullname, user_email, user_affiliation,
                               start_datetime, end_datetime, instCode,
                               kindatList, expName, fileDesc):
        """createGlobalDownloadCmd returns a string representing a global download as is command to run in a particular language.
        
        Inputs:
        
            language - which language to use.  Allowed values are ('python', 'Matlab', 'IDL')
            madrigalUrl - url to madrigal home page where data is
            output - output directory name
            format - 'hdf5', 'ascii', or 'netCDF4'
            user_fullname
            user_email
            user_affiliation
            start_datetime - a datetime object. Reject experiments before that datetime
            end_datetime - a datetime object. Reject experiments after that datetime
            instCode - instrument code (integer)
            kindatList - a list of kindat codes.  An empty list selects all kindats
            expName - filter experiments by the experiment name. Matching is case insensitive and fnmatch characters * and ? are allowed. 
                Empty string is no filtering by experiment name.
            fileDesc - filter files by the file description string. Matching is case insensitive and fnmatch characters * and ? are allowed. 
                Empty string is no filtering by file description.
        """
        if language not in ('python', 'Matlab', 'IDL'):
            raise ValueError('language %s not supported' % (str(language)))
        
        # url
        if language == 'python':
            cmd = 'globalDownload.py --verbose --url=%s ' % (madrigalUrl)
        elif language == 'Matlab':
            cmd = "globalDownload('%s', ...\n " % (madrigalUrl)
        elif language == 'IDL':
            cmd = "madglobaldownload, '%s',  $\n " % (madrigalUrl)
            
        # output
        if language == 'python':
            cmd += '--outputDir=%s ' % (output)
        elif language == 'Matlab':
            cmd += "'%s', ...\n " % (output)
        elif language == 'IDL':
            cmd += "'%s',  $\n " % (output)
            
        # user_fullname
        if language == 'python':
            cmd += '--user_fullname="%s" ' % (user_fullname)
        elif language == 'Matlab':
            cmd += "'%s', ...\n " % (user_fullname)
        elif language == 'IDL':
            cmd += "'%s',  $\n " % (user_fullname)
            
        # user_email
        if language == 'python':
            cmd += '--user_email=%s ' % (user_email)
        elif language == 'Matlab':
            cmd += "'%s', ...\n " % (user_email)
        elif language == 'IDL':
            cmd += "'%s',  $\n " % (user_email)
            
        # user_affiliation
        if language == 'python':
            cmd += '--user_affiliation="%s" ' % (user_affiliation)
        elif language == 'Matlab':
            cmd += "'%s', ...\n " % (user_affiliation)
        elif language == 'IDL':
            cmd += "'%s',  $\n " % (user_affiliation)
            
        # format part 1 (format is not in same order in Matlab and IDL)
        if format not in ('hdf5', 'ascii', 'netCDF4'):
            raise ValueError('format not in hdf5, ascii or netCDF4')
        if language == 'python':
            cmd += '--format="%s" ' % (format)
        elif language == 'Matlab':
            cmd += "'%s', ...\n " % (format)
        
        # start_datetime
        if language == 'python':
            cmd += '--startDate="%s" ' % (start_datetime.strftime('%m/%d/%Y'))
        elif language == 'Matlab':
            cmd += "datenum('%s'), ...\n " % (start_datetime.strftime('%d-%b-%Y %H:%M:%S'))
        elif language == 'IDL':
            cmd += "julday(%i,%i,%i,%i,%i,%i),  $\n " % (start_datetime.month, start_datetime.day,
                                                          start_datetime.year, start_datetime.hour,
                                                          start_datetime.minute, start_datetime.second)
            
        # end_datetime
        if language == 'python':
            cmd += '--endDate="%s" ' % (end_datetime.strftime('%m/%d/%Y'))
        elif language == 'Matlab':
            cmd += "datenum('%s'), ...\n " % (end_datetime.strftime('%d-%b-%Y %H:%M:%S'))
        elif language == 'IDL':
            cmd += "julday(%i,%i,%i,%i,%i,%i),  $\n " % (end_datetime.month, end_datetime.day,
                                                          end_datetime.year, end_datetime.hour,
                                                          end_datetime.minute, end_datetime.second)
            
        # instrument
        if language == 'python':
            cmd += '--inst=%i ' % (instCode)
        elif language == 'Matlab':
            cmd += "%i, ...\n " % (instCode)
        elif language == 'IDL':
            cmd += "%i,  $\n " % (instCode)
            
            
        # kindatList
        if language == 'python':
            if len(kindatList) == 0:
                pass
            else:
                kindatStr = '--kindat='
                for kindat in kindatList:
                    kindatStr += '%i' % (kindat)
                    if kindat != kindatList[-1]:
                        kindatStr += ','
                cmd += '%s ' % (kindatStr)
        elif language == 'Matlab':
            kindatStr = '['
            for kindat in kindatList:
                if kindat == 0:
                    continue
                kindatStr += '%i' % (kindat)
                if kindat != kindatList[-1]:
                    kindatStr += ','
            kindatStr += ']'
            cmd += "%s, ...\n " % (kindatStr)
        elif language == 'IDL':
            # make sure 0 not in list
            try:
                kindatList.remove(0)
            except ValueError:
                pass
            if len(kindatList) == 0:
                kindatStr = 'PTR_NEW()'
            else:
                kindatStr = '['
                for kindat in kindatList:
                    kindatStr += '%i' % (kindat)
                    if kindat != kindatList[-1]:
                        kindatStr += ','
                kindatStr += ']'
            cmd += "%s,  $\n " % (kindatStr)
            
            
        # now deal with IDL format if needed
        if language == 'IDL':
            cmd += "'%s',  $\n " % (format)
            
        # expName
        if language == 'python':
            if len(expName) > 0:
                cmd += '--expName="%s" ' % (expName)
        elif language == 'Matlab':
            expName = expName.replace('*', '.*')
            expName = expName.replace('?', '.?')
            cmd += "'%s', ...\n " % (expName)
        elif language == 'IDL':
            cmd += "'%s',  $\n " % (expName)
            
        # fileDesc
        if language == 'python':
            if len(fileDesc) > 0:
                cmd += '--fileDesc="%s" ' % (fileDesc)
        elif language == 'Matlab':
            fileDesc = fileDesc.replace('*', '.*')
            fileDesc = fileDesc.replace('?', '.?')
            cmd += "'%s') " % (fileDesc)
        elif language == 'IDL':
            cmd += "'%s' " % (fileDesc)
            
        return(cmd)
    
    
    def generateGlobalIsprintScriptFromForm(self, form1, form2, form3, user_fullname,
                                            user_email, user_affiliation):
        """generateGlobalIsprintScriptFromForm converts the three Django forms into arguments so that
        if can then call createGlobalIsprintCmd. Separate forms used because some parts are created by
        Ajax.
        
        form1 is a dict with keys:
            instruments, start_date, end_date, format_select, directory_select, language_select, kindat_select,
            expName, fileDesc, seasonalStartDay, seasonalStartMonth, seasonalEndDay, seasonalEndMonth
        form2 is a dict with keys parameters
        form3 is a dict with keys parm_#, parm_#_lower, parm_#_upper, where # is 1, 2, and 3
        user_fullname, user_email, user_affiliation - strings
            
        """
        instCode = int(form1['instruments'])
        start_datetime = datetime.datetime(form1['start_date'].year, form1['start_date'].month, form1['start_date'].day)
        end_datetime = datetime.datetime(form1['end_date'].year, form1['end_date'].month, form1['end_date'].day)
        format = form1['format_select']
        if format == 'ascii' and form1['directory_select'] == 'File':
            output = 'example.txt'
        else:
            output = '/tmp'
        language = form1['language_select']
        kindatList = [int(kindat) for kindat in form1['kindat_select']]
        expName = form1['expName'].strip()
        fileDesc = form1['fileDesc'].strip()
        seasonalStartDay = int(form1['seasonalStartDay'])
        seasonalStartMonth = int(form1['seasonalStartMonth'])
        seasonalEndDay = int(form1['seasonalEndDay'])
        seasonalEndMonth = int(form1['seasonalEndMonth'])
        if seasonalStartDay == 1 and seasonalStartMonth == 1 and \
            seasonalEndDay == 31 and seasonalEndMonth == 12:
            seasonalStartDate = ''
            seasonalEndDate = ''
        else:
            seasonalStartDate = '%02i/%02i' % (seasonalStartMonth, seasonalStartDay)
            seasonalEndDate = '%02i/%02i' % (seasonalEndMonth, seasonalStartDay)
        madrigalUrl = self._madDB.getTopLevelUrl()
        parmList = form2['parameters']
        filterList = []
        for i in (1,2,3):
            try:
                parm = form3['parm_%i' % (i)]
            except KeyError:
                continue
            if len(parm) == 0:
                continue
            filterStr = '%s,' % (parm)
            try:
                parm_lower = form3['parm_%i_lower' % (i)]
                filterStr += '%s,' % (str(parm_lower))
            except KeyError:
                filterStr += ','
            try:
                parm_upper = form3['parm_%i_upper' % (i)]
                filterStr += '%s' % (str(parm_upper))
            except KeyError:
                pass
            filterList.append(filterStr)
            
            
        return(self.createGlobalIsprintCmd(language, madrigalUrl, parmList, output,
                                           user_fullname, user_email, user_affiliation,
                                           start_datetime, end_datetime, instCode,
                                           filterList, kindatList, expName, fileDesc,
                                           seasonalStartDate, seasonalEndDate, format))
    
    
    def generateDownloadFileScriptFromForm(self, form, user_fullname,
                                           user_email, user_affiliation):
        """generateDownloadFileScriptFromForm converts the Django form into arguments so that
        if can then call createGlobalDownloadCmd.
        
        form is a dict with keys:
            instruments, start_date, end_date, format_select, language_select, kindat_select,
            expName, fileDesc
        user_fullname, user_email, user_affiliation - strings
            
        """
        instCode = int(form['instruments'])
        start_datetime = datetime.datetime(form['start_date'].year, form['start_date'].month, form['start_date'].day)
        end_datetime = datetime.datetime(form['end_date'].year, form['end_date'].month, form['end_date'].day)
        format = form['format_select']
        language = form['language_select']
        kindatList = [int(kindat) for kindat in form['kindat_select']]
        expName = form['expName'].strip()
        fileDesc = form['fileDesc'].strip()
        madrigalUrl = self._madDB.getTopLevelUrl()
        return(self.createGlobalDownloadCmd(language, madrigalUrl, '/tmp', format,
                               user_fullname, user_email, user_affiliation,
                               start_datetime, end_datetime, instCode,
                               kindatList, expName, fileDesc))
    
    
    def getSingleRedirectList(self):
        """getSingleRedirectList returns a list with tuples (kinst, url) where url is url to redirect single UI
        to if instrument not local. If no redirect needed because instrument local, url is empty string
        """
        madInstData = madrigal.metadata.MadrigalInstrumentData(self._madDB, True)
        siteObj = madrigal.metadata.MadrigalSite(self._madDB)
        siteID = self._madDB.getSiteID()
        
        # create a dict with key = siteID, value = redirect url for speed
        getStr = '?isGlobal=True&categories=%i&instruments=%i'
        addUrl = django.urls.reverse('view_single')
        cedarUrl = 'http://cedar.openmadrigal.org/' + addUrl + getStr
        siteDict = {}
        for thisSiteID, siteDesc in siteObj.getSiteList():
            if thisSiteID == siteID:
                siteDict[thisSiteID] = '' # local case
            elif siteObj.getSiteVersion(thisSiteID) == '2.6':
                # redirect to cedar because other site below Madrigal 3
                siteDict[thisSiteID] = cedarUrl
            else:
                if siteObj.getSiteServer(thisSiteID).find('http') == -1:
                    siteDict[thisSiteID] = 'http://' + siteObj.getSiteServer(thisSiteID)
                else:
                    siteDict[thisSiteID] = siteObj.getSiteServer(thisSiteID)
                secondPart = siteObj.getSiteDocRoot(thisSiteID) + addUrl + getStr
                if secondPart[0] == '/':
                    siteDict[thisSiteID] += secondPart
                else:
                    siteDict[thisSiteID] += '/' + secondPart
        
        
        retList = []
        for kinst, desc, thisSiteID in madInstData.getInstruments():
            if self._instObj.getCategoryId(kinst) is None:
                continue
            if len(siteDict[thisSiteID]) > 0:
                if siteDict[thisSiteID].find('=%i') != -1:
                    url = siteDict[thisSiteID] % (self._instObj.getCategoryId(kinst), kinst)
                else:
                    url = siteDict[thisSiteID]
            else:
                url = ''
            retList.append((kinst, url))
            
        return(retList)
    
    
    def getMonths(self, kinst, year, optimize=True):
        """getMonths returns a list of tuples of (monthNumber, monthName) where monthNumber
        is 1-12, and monthName is the form January, Febuary, etc. for the the months where
        there is local data for kinst & year combination
        
        Inputs:
            kinst - instrument id (int)
            year - year (int)
            optimize - if True, only start search at beginning of year.  But may miss long experiments,
                so if optimization if False, starts at beginning
        """
        tempDict = {} # dict with key = month number, value = month name
        sDT = datetime.datetime(year,1,1)
        eDT = datetime.datetime(year,12,31,23,59,59)
        madroot = self._madDB.getMadroot()
        if self._madExpObjDate is None:
            self._madExpObjDate = madrigal.metadata.MadrigalExperiment(self._madDB)
        if optimize:
            startIndex = self._madExpObjDate.getStartPosition(sDT)
        else:
            startIndex = 0
        for i in range(startIndex, self._madExpObjDate.getExpCount()):
            thisKinst = self._madExpObjDate.getKinstByPosition(i)
            if kinst != thisKinst:
                continue
            thisSDTList = self._madExpObjDate.getExpStartDateTimeByPosition(i)
            thisSDT = datetime.datetime(*thisSDTList[0:6])
            thisEDTList = self._madExpObjDate.getExpEndDateTimeByPosition(i)
            thisEDT = datetime.datetime(*thisEDTList[0:6])
            if thisEDT < sDT:
                continue
            if thisSDT > eDT:
                continue
            # check for security
            security = self._madExpObjDate.getSecurityByPosition(i)
            if not self.isTrusted(): 
                if security not in (0,2):
                    continue
            else:
                if security not in (0,1,2,3):
                    continue
            if thisSDT.year == year:
                startMonth = thisSDT.month
            else:
                startMonth = 1
            if thisEDT.year == year:
                endMonth = thisEDT.month
            else:
                endMonth = 12
            monthList = list(range(startMonth, endMonth + 1))
            for thisMonth in monthList:
                if thisMonth not in list(tempDict.keys()):
                    tempDict[thisMonth] = calendar.month_name[thisMonth]
                
        monthKeys = list(tempDict.keys())
        monthKeys.sort()
        retList = [(monthKey, tempDict[monthKey]) for monthKey in monthKeys]
        return(retList)
    
    
    def getDays(self, kinst, year, month=None, optimize=True):
        """getDays returns a sorted list of datetime.date objects where
        there is local data for kinst & year & possibly month combination
        
        Inputs:
            kinst - instrument id (int)
            year - year (int)
            month (1-12) if None, include all months
            optimize - if True, only start search at beginning of year.  But may miss long experiments,
                so if optimization if False, starts at beginning
        """
        retList = []
        sDT = datetime.datetime(year,1,1)
        eDT = datetime.datetime(year,12,31,23,59,59)
        if self._madExpObjDate is None:
            self._madExpObjDate = madrigal.metadata.MadrigalExperiment(self._madDB)
        if optimize:
            startIndex = self._madExpObjDate.getStartPosition(sDT)
        else:
            startIndex = 0
        for i in range(startIndex, self._madExpObjDate.getExpCount()):
            thisKinst = self._madExpObjDate.getKinstByPosition(i)
            if kinst != thisKinst:
                continue
            thisSDTList = self._madExpObjDate.getExpStartDateTimeByPosition(i)
            thisSDT = datetime.datetime(*thisSDTList[0:6])
            thisEDTList = self._madExpObjDate.getExpEndDateTimeByPosition(i)
            thisEDT = datetime.datetime(*thisEDTList[0:6])
            if thisEDT < sDT:
                continue
            if thisSDT > eDT:
                continue
            # check for security
            security = self._madExpObjDate.getSecurityByPosition(i)
            if not self.isTrusted():
                if security not in (0,2):
                    continue
            else:
                if security not in (0,1,2,3):
                    continue
            # loop over all days
            delta = datetime.timedelta(days=1)
            loopDT = max(sDT, datetime.datetime(thisSDT.year, thisSDT.month, thisSDT.day))
            while (loopDT <= thisEDT):
                if loopDT > eDT:
                    break
                if not month is None:
                    if month > loopDT.month:
                        loopDT += delta
                        continue
                    elif month < loopDT.month:
                        break
                thisDate = loopDT.date()
                if thisDate not in retList:
                    retList.append(thisDate)
                loopDT += delta
                
                
        retList.sort()
        return(retList)
    
    
    
    def getExperimentList(self, kinstList, startDT, endDT, localOnly):
        """getExperimentList returns a sorted list of tuples of (expId, expUrl, expName, instName, kinst, 
        expStartDT, expEndDT, siteId, siteName)
        
        Inputs:
            kinstList -  a list of instrument id (int) - may include 0
            startDT - start datetime to search
            endDT - end datetime to search
            localOnly - if True, only search locally. If False, search globally
        """
        retList = []
        madroot = self._madDB.getMadroot()
        siteId = self._madDB.getSiteID()
        siteObj = madrigal.metadata.MadrigalSite(self._madDB)
        if localOnly:
            expTabFile = os.path.join(madroot, 'metadata/expTab.txt')
        else:
            expTabFile = os.path.join(madroot, 'metadata/expTabAll.txt')
        madExpObjDate = madrigal.metadata.MadrigalExperiment(self._madDB, expTabFile)
        startIndex = madExpObjDate.getStartPosition(startDT)
        for i in range(startIndex, madExpObjDate.getExpCount()):
            thisKinst = madExpObjDate.getKinstByPosition(i)
            if thisKinst not in kinstList and 0 not in kinstList:
                continue
            thisSDTList = madExpObjDate.getExpStartDateTimeByPosition(i)
            thisSDT = datetime.datetime(*thisSDTList[0:6])
            thisEDTList = madExpObjDate.getExpEndDateTimeByPosition(i)
            thisEDT = datetime.datetime(*thisEDTList[0:6])
            if thisEDT < startDT:
                continue
            if thisSDT > endDT:
                break
            # check for security
            security = madExpObjDate.getSecurityByPosition(i)
            if not self.isTrusted():
                if security not in (0,2):
                    continue
            else:
                if security not in (0,1,2,3):
                    continue
            thisSiteId = madExpObjDate.getExpSiteIdByPosition(i)
            if siteId == thisSiteId:
                isLocal = True
            else:
                isLocal = False
            thisExpId = madExpObjDate.getExpIdByPosition(i)
            thisExpPath = madExpObjDate.getExpPathByPosition(i)
            thisExpName = madExpObjDate.getExpNameByPosition(i)
            if isLocal:
                thisExpUrl = django.urls.reverse('show_experiment') + \
                    '?experiment_list=%i' % (thisExpId)
            elif siteObj.getSiteVersion(thisSiteId) == '2.6':
                if siteObj.getSiteServer(thisSiteId).find('http') == -1:
                    thisExpUrl = 'http://' + os.path.join(siteObj.getSiteServer(thisSiteId),
                                              siteObj.getSiteRelativeCGI(thisSiteId),
                                              'madExperiment.cgi?exp=%s' % (thisExpPath))
                else:
                    thisExpUrl = os.path.join(siteObj.getSiteServer(thisSiteId),
                                              siteObj.getSiteRelativeCGI(thisSiteId),
                                              'madExperiment.cgi?exp=%s' % (thisExpPath))
                thisExpUrl += '&displayLevel=0&expTitle=%s' % (urllib.parse.quote(thisExpName))
            else:
                # remote Madrigal 3.0 site
                baseUrl = os.path.basename(django.urls.reverse('show_experiment'))
                thisExpUrl = baseUrl + '?experiment_list=%s' % (thisExpPath)
                if siteObj.getSiteServer(thisSiteId).find('http') == -1:
                    thisSiteUrl = 'http://%s' % (siteObj.getSiteServer(thisSiteId))
                else:
                    thisSiteUrl = siteObj.getSiteServer(thisSiteId)
                relativeUrl = siteObj.getSiteDocRoot(thisSiteId)
                if relativeUrl not in ('', None):
                    thisSiteUrl = os.path.join(thisSiteUrl, relativeUrl)
                if thisSiteUrl[-1] != '/' and thisExpUrl[0] != '/':
                    thisSiteUrl += '/'
                thisExpUrl = thisSiteUrl + thisExpUrl
                
            thisSiteName = siteObj.getSiteName(thisSiteId)
            instName = self._instObj.getInstrumentName(thisKinst)
            
            retList.append((thisExpId, thisExpUrl, thisExpName, instName, thisKinst, 
                            thisSDT.strftime('%Y-%m-%d %H:%M:%S'), thisEDT.strftime('%Y-%m-%d %H:%M:%S'),
                            thisSiteId, thisSiteName))
                
        return(retList)
    
    
    
    def getExpsOnDate(self, kinst, year, month, day, optimize=True):
        """getExpsOnDate returns a sorted list of tuples of (expId, expDesc, expDir, pi_name, pi_email)
        
        Inputs:
            kinst - instrument id (int)
            year - year (int)
            month - month (int)
            day - day (int)
            optimize - if True, only start search at beginning of day.  But may miss long experiments,
                so if optimization if False, starts at beginning
        """
        retList = []
        sDT = datetime.datetime(year,month,day)
        eDT = datetime.datetime(year,month,day,23,59,59)
        if self._madExpObjDate is None:
            self._madExpObjDate = madrigal.metadata.MadrigalExperiment(self._madDB)
        if optimize:
            startIndex = self._madExpObjDate.getStartPosition(sDT)
        else:
            startIndex = 0
        for i in range(startIndex, self._madExpObjDate.getExpCount()):
            thisKinst = self._madExpObjDate.getKinstByPosition(i)
            if kinst != thisKinst:
                continue
            thisSDTList = self._madExpObjDate.getExpStartDateTimeByPosition(i)
            thisSDT = datetime.datetime(*thisSDTList[0:6])
            thisEDTList = self._madExpObjDate.getExpEndDateTimeByPosition(i)
            thisEDT = datetime.datetime(*thisEDTList[0:6])
            if thisEDT < sDT:
                continue
            if thisSDT > eDT:
                continue
            # check for security
            security = self._madExpObjDate.getSecurityByPosition(i)
            if not self.isTrusted():
                if security not in (0,2):
                    continue
            else:
                if security not in (0,1,2,3):
                    continue
            thisExpId = self._madExpObjDate.getExpIdByPosition(i)
            thisExpName = self._madExpObjDate.getExpNameByPosition(i)
            thisExpDesc = '%s: %s-%s' % (thisExpName, thisSDT.strftime('%Y-%m-%d %H:%M:%S'),
                                         thisEDT.strftime('%Y-%m-%d %H:%M:%S'))
            thisExpDir = self._madExpObjDate.getExpDirByPosition(i)
            thisExpPI = self._madExpObjDate.getPIByPosition(i)
            thisExpPIEmail = self._madExpObjDate.getPIEmailByPosition(i)
            if thisExpPI in (None, ''):
                thisExpPI = self._instObj.getContactName(kinst)
                thisExpPIEmail = self._instObj.getContactEmail(kinst)
            retList.append((thisExpId, thisExpDesc, thisExpDir))
                
        return(retList)
    
    
    
    def getFileFromExpDir(self, expDir, kinst, includeNonDefault=False):
        """getFileFromExpDir returns a list of tuples of (basename, fileDesc)
        
        Inputs:
            expDir - full path to exp directory
            kinst - instrument id (used to look up kindat descriptions)
            includeNonDefault - if True, include variant and history files.  If False
                (the default), do not
        """
        retList = []
        realTimeList = [] # in case no default files
        if not os.access(os.path.join(expDir, 'fileTab.txt'), os.R_OK):
            # no files in this experiment
            return(retList)
        madFileObj = madrigal.metadata.MadrigalMetaFile(self._madDB, os.path.join(expDir, 'fileTab.txt'))
        for i in range(madFileObj.getFileCount()):
            if madFileObj.getAccessByPosition(i) == 1 and not self.isTrusted():
                continue
            category = madFileObj.getCategoryByPosition(i)
            if category in (2,3) and not includeNonDefault:
                continue
            basename = madFileObj.getFilenameByPosition(i)
            kindat = madFileObj.getKindatByPosition(i)
            kindatDesc = self._madKindatObj.getKindatDescription(kindat, kinst)
            status = madFileObj.getStatusByPosition(i)
            fileDesc = '%s: %s - %s' % (basename, kindatDesc, status)
            if category != 4:
                retList.append((basename, fileDesc))
            else:
                realTimeList.append((basename, fileDesc))
            
        if len(retList) > 0:
            return(retList)
        else:
            return(realTimeList)
        
    
    def getExpInfoFromExpID(self, expID):
        """getExpInfoFromExpID returns a tuple of (pi_name, pi_email, expUrl, kinst, expDesc, kinstDesc) for given expID
        
        expUrl is url from getRealExpUrlByExpId
        
        Inputs:
            expID - experimentID (int)
        """
        expID = int(expID)
        if self._madExpObjExpID is None:
            self._madExpObjExpID = madrigal.metadata.MadrigalExperiment(self._madDB)
        kinst = self._madExpObjExpID.getKinstByExpId(expID)
        kinstDesc = self._instObj.getInstrumentName(kinst)
        expPI = self._madExpObjExpID.getPIByExpId(expID)
        expPIEmail = self._madExpObjExpID.getPIEmailByExpId(expID)
        expUrl = self._madExpObjExpID.getRealExpUrlByExpId(expID)
        if expPI in (None, ''):
            expPI = self._instObj.getContactName(kinst)
            expPIEmail = self._instObj.getContactEmail(kinst)
        thisSDTList = self._madExpObjExpID.getExpStartDateTimeByExpId(expID)
        thisSDT = datetime.datetime(*thisSDTList[0:6])
        thisEDTList = self._madExpObjExpID.getExpEndDateTimeByExpId(expID)
        thisEDT = datetime.datetime(*thisEDTList[0:6])
        thisExpName = self._madExpObjExpID.getExpNameByExpId(expID)
        thisExpDesc = '%s: %s-%s' % (thisExpName, thisSDT.strftime('%Y-%m-%d %H:%M:%S'),
                                     thisEDT.strftime('%Y-%m-%d %H:%M:%S'))
        
        return((expPI, expPIEmail, expUrl, kinst, thisExpDesc, kinstDesc))
    
    
    def getExpIDFromExpPath(self, expPath, matchAnyExpNum=False):
        """getExpIDFromExpPath returns the expId for given expPath (starts with 'experiments')
        
        If matchAnyExpNum is False, it will only match the right experiments* directory (default).
        It True, matches via re to experiments[0-9]*/<remaining exp path>
        
        Returns None if not found
        
        Inputs:
            expPath - experiment path (starts with 'experiments')
        """
        madExpObj = madrigal.metadata.MadrigalExperiment(self._madDB)
        if matchAnyExpNum:
            expPathRE = 'experiments[0-9]*/' + expPath[expPath.find('/')+1:]
        expPathBase = os.path.basename(expPath)
        for i in range(madExpObj.getExpCount()):
            if not matchAnyExpNum:
                if madExpObj.getExpPathByPosition(i) == expPath:
                    return(madExpObj.getExpIdByPosition(i))
            else:
                if len(re.findall(expPathRE, madExpObj.getExpPathByPosition(i))) > 0:
                    thisBase = os.path.basename(madExpObj.getExpPathByPosition(i))
                    if expPathBase == thisBase:
                        return(madExpObj.getExpIdByPosition(i))
        
        return(None)
    
    
    def getInfoFromFile(self, filePath):
        """getInfoFromFile returns a tuple of (expName, kindatDesc) for a given input file
        """
        expDir = os.path.dirname(filePath)
        basename = os.path.basename(filePath)
        madExpObj = madrigal.metadata.MadrigalExperiment(self._madDB, os.path.join(expDir, 'expTab.txt'))
        expName = madExpObj.getExpNameByPosition(0)
        kinst = madExpObj.getKinstByPosition(0)
        madFileObj = madrigal.metadata.MadrigalMetaFile(self._madDB, os.path.join(expDir, 'fileTab.txt'))
        kindat = madFileObj.getKindatByFilename(basename)
        kindatDesc = self._madKindatObj.getKindatDescription(kindat, kinst)
        return((expName, kindatDesc))
    
    
    def getFormatsAvailable(self, expID, basename):
        """getFormatsAvailable returns a list of alternate formats available
        in near real time for a given Madrigal Hdf5 file.  If file greater than
        max, then cached files must already exist.  Returns up to two items:
        ['ascii', 'netCDF4']
        """
        maxSize = 50000000 # 50 MB cutoff
        retList = []
        if self._madExpObjExpID is None:
            self._madExpObjExpID = madrigal.metadata.MadrigalExperiment(self._madDB)
        expDir = self._madExpObjExpID.getExpDirByExpId(expID)
        if expDir is None:
            return([]) # bad expID
        fullname = os.path.join(expDir, basename)
        if os.path.getsize(fullname) < maxSize:
            return(['ascii', 'netCDF4'])
        
        cachedFile = os.path.join(expDir, 'overview', basename + '.txt.gz')
        if os.path.exists(cachedFile):
            retList.append('ascii')
            
        cachedFile = os.path.join(expDir, 'overview', basename + '.nc')
        if os.path.exists(cachedFile):
            retList.append('netCDF4')
            
        return(retList)
        
        
        
    def getFileFromExpID(self, expID, includeNonDefault=False):
        """getFileFromExpDir returns a list of tuples of (basename, fileDesc)
        
        Inputs:
            expID - experimentID (int)
            includeNonDefault - if True, include variant and history files.  If False
                (the default), do not
        """
        retList = []
        realTimeList = [] # in case no default files
        if self._madExpObjExpID is None:
            self._madExpObjExpID = madrigal.metadata.MadrigalExperiment(self._madDB)
        expDir = self._madExpObjExpID.getExpDirByExpId(expID)
        if expDir is None:
            # no files in this experiment
            return(retList)
        kinst = self._madExpObjExpID.getKinstByExpId(expID)
        
        if not os.access(os.path.join(expDir, 'fileTab.txt'), os.R_OK):
            # no files in this experiment
            return(retList)
        
        madFileObj = madrigal.metadata.MadrigalMetaFile(self._madDB, os.path.join(expDir, 'fileTab.txt'))
        for i in range(madFileObj.getFileCount()):
            if madFileObj.getAccessByPosition(i) == 1 and not self.isTrusted():
                continue
            category = madFileObj.getCategoryByPosition(i)
            if category in (2,3) and not includeNonDefault:
                continue
            if category == 2:
                categoryStr = '<variant file> '
            elif category == 3:
                categoryStr = '<history file> '
            else:
                categoryStr = ''
            basename = madFileObj.getFilenameByPosition(i)
            kindat = madFileObj.getKindatByPosition(i)
            kindatDesc = self._madKindatObj.getKindatDescription(kindat, kinst)
            status = madFileObj.getStatusByPosition(i)
            fileDesc = '%s: %s%s - %s' % (basename, categoryStr, kindatDesc, status)
            if category != 4:
                retList.append((basename, fileDesc))
            else:
                if includeNonDefault:
                    retList.append((basename, fileDesc))
                realTimeList.append((basename, fileDesc))
            
        if len(retList) > 0:
            return(retList)
        else:
            return(realTimeList)
        
        
    def getSiteInfo(self):
        """getSiteInfo returns a tuple of two items:
            1. local site name
            2. list of tuples of (siteName, url) of non-local sites
        """
        siteID = self._madDB.getSiteID()
        siteObj = madrigal.metadata.MadrigalSite(self._madDB)
        siteName = siteObj.getSiteName(siteID)
        retList = []
        siteList = siteObj.getSiteList()
        for thisSiteID, thisSiteName in siteList:
            if thisSiteID == siteID:
                continue
            thisSiteServer = siteObj.getSiteServer(thisSiteID)
            thisSiteDocRoot = siteObj.getSiteDocRoot(thisSiteID)
            if thisSiteServer.find('http') == -1:
                thisSiteUrl = urllib.parse.urlunparse(('http', thisSiteServer, thisSiteDocRoot, '','',''))
            else:
                thisSiteUrl = urllib.parse.urljoin(thisSiteServer, thisSiteDocRoot)
            if thisSiteUrl[-1] != '/':
                thisSiteUrl += '/'
            retList.append((thisSiteName, thisSiteUrl))
        return((siteName, retList))
    
    
    def downloadFileAsIs(self, expId, basename, user_fullname, user_email, user_affiliation):
        """downloadFileAsIs returns a path to a Madrigal file to download as is (that is, with parms in file, and no filters)
        
        Inputs:
            expId - experiment id of experiment
            basename - basename of file.  May have .txt or .nc extension, in which case Hdf5 file is converted
            user_fullname, user_email, user_affiliation - user identification strings
        """
        self.cleanStage()
        hdf5Extensions = ('.hdf5', '.h5', '.hdf')
        fileName, fileExtension = os.path.splitext(basename)
        if self._madExpObjExpID is None:
            self._madExpObjExpID = madrigal.metadata.MadrigalExperiment(self._madDB)
        expDir = self._madExpObjExpID.getExpDirByExpId(int(expId))
        if expDir is None:
            raise ValueError('No expDir found for exp_id %i' % (int(expId)))
        if fileExtension in hdf5Extensions:
            baseHdf5 = basename
        else:
            # we need to search for the hdf5 basename
            madFileObj = madrigal.metadata.MadrigalMetaFile(self._madDB, os.path.join(expDir, 'fileTab.txt'))
            baseHdf5 = None
            for i in range(madFileObj.getFileCount()):
                thisFileName, thisFileExt = os.path.splitext(madFileObj.getFilenameByPosition(i))
                if thisFileName == fileName and thisFileExt in hdf5Extensions:
                    baseHdf5 = madFileObj.getFilenameByPosition(i)
                    break
        if baseHdf5 is None:
            raise ValueError('No valid file for %s found in %s' % (basename, expDir))
        if basename == baseHdf5:
            fullFilename = os.path.join(expDir, basename)
            fullHdf5Filename = fullFilename
            tmpDir = None
        else:
            fullHdf5Filename = os.path.join(expDir, baseHdf5)
            # create tmp dir if needed
            tmpDir = os.path.join(self._madDB.getMadroot(), 'experiments/stage')
            try:
                os.mkdir(tmpDir)
            except:
                pass
            fullFilename = os.path.join(tmpDir, basename)
            if os.access(fullFilename, os.R_OK):
                try:
                    os.remove(fullFilename)
                except:
                    pass
            if fileExtension == '.txt':
                cachedFile = os.path.join(expDir, 'overview', baseHdf5 + '.txt.gz')
                if os.access(cachedFile, os.R_OK):
                    fullFilename += '.gz'
                    shutil.copy(cachedFile, fullFilename)
                else:
                    madrigal.cedar.convertToText(fullHdf5Filename, fullFilename)
            elif fileExtension == '.nc':
                cachedFile = os.path.join(expDir, 'overview', baseHdf5 + '.nc')
                if os.access(cachedFile, os.R_OK):
                    shutil.copy(cachedFile, fullFilename)
                else:
                    try:
                        madrigal.cedar.convertToNetCDF4(fullHdf5Filename, fullFilename)
                    except IOError:
                        cedarObj = madrigal.cedar.MadrigalCedarFile(fullHdf5Filename)
                        cedarObj.write('netCDF4', fullFilename)
                
        # log access
        self.logDataAccess(fullHdf5Filename, user_fullname, user_email, user_affiliation)
        
        return(fullFilename)
    
    
    
    def downloadFullFileAsIs(self, fullHdf5Filename, format, user_fullname, user_email, user_affiliation):
        """downloadFullFileAsIs is similar to downloadFileAsIs with fullFilename input instead of expId .
        
        Returns a path to a Madrigal file to download as is (that is, with parms in file, and no filters)
        
        Inputs:
            fullHdf5Filename - full path to Madrigal Hdf5 file
            format - 'hdf5', 'netCDF4', or 'ascii'
            user_fullname, user_email, user_affiliation - user identification strings
        """
        self.cleanStage()
        if format not in ('hdf5', 'netCDF4', 'ascii'):
            raise ValueError('Illegal format %s' % (str(format)))
        if not os.access(fullHdf5Filename, os.R_OK):
            raise IOError('Unable to find Hdf5 file %s' % (str(fullHdf5Filename)))
        if format == 'hdf5':
            fullFilename = fullHdf5Filename
            tmpDir = None
        else:
            # dynamically create file
            if format == 'netCDF4':
                thisExt = '.nc'
            elif format == 'ascii':
                thisExt = '.txt'
            # create tmp dir if needed
            tmpDir = os.path.join(self._madDB.getMadroot(), 'experiments/stage')
            try:
                os.mkdir(tmpDir)
            except:
                pass
            base, file_extension = os.path.splitext(fullHdf5Filename)
            basename = os.path.basename(base + thisExt)
            fullFilename = os.path.join(tmpDir, basename)
            if os.access(fullFilename, os.R_OK):
                try:
                    os.remove(fullFilename)
                except:
                    pass

            if format == 'ascii':
                cachedFile = os.path.join(os.path.dirname(fullHdf5Filename), 'overview', 
                                          os.path.basename(fullHdf5Filename) + '.txt.gz')
                if os.access(cachedFile, os.R_OK):
                    fullFilename += '.gz'
                    shutil.copy(cachedFile, fullFilename)
                else:
                    madrigal.cedar.convertToText(fullHdf5Filename, fullFilename)
            elif format == 'netCDF4':
                cachedFile = os.path.join(os.path.dirname(fullHdf5Filename), 'overview', 
                                          os.path.basename(fullHdf5Filename) + '.nc')
                if os.access(cachedFile, os.R_OK):
                    shutil.copy(cachedFile, fullFilename)
                else:
                    try:
                        madrigal.cedar.convertToNetCDF4(fullHdf5Filename, fullFilename)
                    except IOError:
                        cedarObj = madrigal.cedar.MadrigalCedarFile(fullHdf5Filename)
                        cedarObj.write('netCDF4', fullFilename)
                
        # log access
        self.logDataAccess(fullHdf5Filename, user_fullname, user_email, user_affiliation)
        
        return(fullFilename)
    
    
    def downloadMultipleFiles(self, fileList, format, user_fullname, user_email, user_affiliation):
        """downloadMultipleFiles downloads multiple files in tarred format
        
        Returns a path to a Madrigal tarred file to download in given format as is (that is, with parms in file, and no filters)
        
        Inputs:
            fileList - list of full paths to Madrigal Hdf5 files
            format - 'hdf5', 'netCDF4', or 'ascii'
            user_fullname, user_email, user_affiliation - user identification strings
        """
        self.cleanStage()
        if format not in ('hdf5', 'netCDF4', 'ascii'):
            raise ValueError('Illegal format %s' % (str(format)))
        # create tmp dir if needed
        tmpDir = os.path.join(self._madDB.getMadroot(), 'experiments/stage')
        try:
            os.mkdir(tmpDir)
        except:
            pass
        # be sure no duplicate file names
        basenameList = []
        if format == 'hdf5':
            finalFileList = []
            for thisFile in fileList:
                basename = os.path.basename(thisFile)
                dirname = os.path.dirname(thisFile)
                if basename in basenameList:
                    basename = self.modifyBasename(basename)
                    fullFilename = os.path.join(tmpDir, basename)
                    shutil.copy(thisFile, fullFilename)
                else:
                    fullFilename = os.path.join(dirname, basename)
                basenameList.append(basename)
                finalFileList.append(fullFilename)
                
        else:
            # dynamically create files
            if format == 'netCDF4':
                thisExt = '.nc'
            elif format == 'ascii':
                thisExt = '.txt'
            finalFileList = []
            for thisFile in fileList:
                if not os.access(thisFile, os.R_OK):
                    raise IOError('Unable to find Hdf5 file %s' % (str(thisFile)))
                base, file_extension = os.path.splitext(thisFile)
                basename = os.path.basename(base + thisExt)
                if basename in basenameList:
                    basename = self.modifyBasename(basename)
                basenameList.append(basename)
                fullFilename = os.path.join(tmpDir, basename)
                
                if format == 'ascii':
                    cachedFile = os.path.join(os.path.dirname(thisFile), 'overview', 
                                              os.path.basename(thisFile) + '.txt.gz')
                    if os.access(cachedFile, os.R_OK):
                        fullFilename += '.gz'
                        if not os.access(fullFilename, os.R_OK):
                            shutil.copy(cachedFile, fullFilename)
                    else:
                        madrigal.cedar.convertToText(thisFile, fullFilename)
                elif format == 'netCDF4':
                    cachedFile = os.path.join(os.path.dirname(thisFile), 'overview', 
                                              os.path.basename(thisFile) + '.nc')
                    if os.access(cachedFile, os.R_OK):
                        if not os.access(fullFilename, os.R_OK):
                            shutil.copy(cachedFile, fullFilename)
                    else:
                        try:
                            madrigal.cedar.convertToNetCDF4(thisFile, fullFilename)
                        except IOError:
                            cedarObj = madrigal.cedar.MadrigalCedarFile(thisFile)
                            cedarObj.write('netCDF4', fullFilename)
                finalFileList.append(fullFilename)
                
        # create tar file
        now = datetime.datetime.now()
        tar_filename = os.path.join(tmpDir, 'madrigalFiles_%s.tar' % (now.strftime('%Y%m%dT%H%M%S')))
        tar = tarfile.open(tar_filename, "w")
        for thisFile in finalFileList:
            # log access
            self.logDataAccess(thisFile, user_fullname, user_email, user_affiliation)
            tar.add(thisFile)
            # let clean stage do this - safer
        return(tar_filename)
        
    
    
    
    def printFileAsIs(self, fullFilename, user_fullname, user_email, user_affiliation, html=True):
        """printFileAsIs returns the full path to a temp file representing file as plain text or html to print as is (that is, with parms rom file, and no filters)
        
        Inputs:
            fullFilename - full path to Madrigal Hdf5 file to convert to string
            user_fullname, user_email, user_affiliation - user identification strings
            html - if True (the default) return as Html with popup parm names.  If False, pure text
        """
        self.cleanStage()
        
        # create tmp dir if needed
        tmpDir = os.path.join(self._madDB.getMadroot(), 'experiments/stage')
        try:
            os.mkdir(tmpDir)
        except:
            pass
        
        fileName, fileExtension = os.path.splitext(fullFilename)
        fullTmpFilename = os.path.join(tmpDir, os.path.basename(fileName + '.txt'))

        if os.access(fullTmpFilename, os.R_OK):
            try:
                os.remove(fullTmpFilename)
            except:
                pass
        if html:
            summary = 'html'
        else:
            summary = 'plain'
        madrigal.cedar.convertToText(fullFilename, fullTmpFilename, summary=summary)
                
        # log access
        self.logDataAccess(fullFilename, user_fullname, user_email, user_affiliation)
        
        return(fullTmpFilename)
    
    
    def listRecords(self, fullFilename):
        """listRecords returns the list records html for fullFilename
        """
        # check if record plots exist
        basename = os.path.basename(fullFilename)
        thisDir = os.path.dirname(fullFilename)
        pngFiles = glob.glob(os.path.join(thisDir, 'plots', basename, 'records/*.png'))
        if len(pngFiles) > 0:
            url = '<a href="javascript:plotRecno(%i)">View record plot</a>'
        else:
            url = None
        
        output = os.path.join(tempfile.gettempdir(), 'tmp_%i.txt' % (random.randint(0,999999)))
        
        madrigal.cedar.listRecords(fullFilename, output, url)
        
        with open(output) as f:
            text = f.read()
            
        os.remove(output)
        return(text.strip())
        
    
    
    def downloadIsprintFileFromIsprintForm(self, isprintForm, user_fullname, user_email, user_affiliation):
        """downloadIsprintFileFromIsprintForm returns a full path to the temp file is experiments/stage created by isprint to download.
        
        Inputs:
            isprintForm - the django form that encapsulates all information from get_advanced web page.  
            user_fullname, user_email, user_affiliation - user identification strings
        """
        # defaults arguments
        showHeaders=False
        missing=None
        assumed=None
        knownbad=None
        
        orgFilename = isprintForm['fullFilename']
        requestedParms = isprintForm['parameters']
        # make unique
        uniqueRequestedParms = []
        for s in requestedParms:
            if type(s) in (bytes, numpy.bytes_):
                s = s.decode("ascii")
            asciiParm = s.lower().strip()
            if asciiParm not in uniqueRequestedParms:
                uniqueRequestedParms.append(asciiParm)
        start_date = isprintForm['start_date']
        end_date = isprintForm['end_date']
        
        format = isprintForm['formats']
        # create name of temp file
        basename_noext, ext = os.path.splitext(os.path.basename(orgFilename))
        randint = random.randint(0,999999)
        if format in ('ascii', 'netCDF4'):
            # need new basename
            if format == 'ascii':
                basename = basename_noext + '_%06i.txt' % (randint)
            else:
                basename = basename_noext + '_%06i.nc' % (randint)
        else:
            basename = basename_noext + '_%06i.hdf5' % (randint)
        tmpFile = os.path.join(self._madDB.getMadroot(), 'experiments/stage', basename)
        
        if format == 'ascii':
            # reset defaults
            showHeaders = isprintForm['showHeaders']
            missing = isprintForm['missing']
            assumed = isprintForm['missing']
            knownbad = isprintForm['missing']
            
        # next task - create a list of filters, but only if actually modified
        madFilters = []
        
        madFileObj = madrigal.data.MadrigalFile(orgFilename, self._madDB) # used to determine default values
        
        # check if we need a time filer
        earliestTime = madFileObj.getEarliestTime()
        latestTime = madFileObj.getLatestTime()
        earliestDT = datetime.datetime(*earliestTime)
        latestDT = datetime.datetime(*latestTime)
        earliest_unix = calendar.timegm(earliestDT.timetuple())
        latest_unix = calendar.timegm(latestDT.timetuple())
        start_unix = calendar.timegm(start_date.timetuple())
        end_unix = calendar.timegm(end_date.timetuple())
        
        if earliest_unix < start_unix or latest_unix > end_unix:
            # we need a time filter
            madFilters.append(madrigal.derivation.MadrigalFilter('ut1_unix', [(start_unix, end_unix)]))
            
        # altitude filter
        if 'min_alt' in isprintForm:
            file_min_alt = madFileObj.getMinValidAltitude()
            file_max_alt = madFileObj.getMaxValidAltitude()
            try:
                min_alt = float(isprintForm['min_alt'])
            except ValueError:
                min_alt = float('nan')
            try:
                max_alt = float(isprintForm['max_alt'])
            except ValueError:
                max_alt = float('nan')
            is_needed = False
            if not math.isnan(min_alt):
                if min_alt > file_min_alt + 1.0E-6:
                    is_needed = True
            if not math.isnan(max_alt):
                if max_alt < file_max_alt - 1.0E-6:
                    is_needed = True
            if is_needed:
                madFilters.append(madrigal.derivation.MadrigalFilter('gdalt', [(min_alt, max_alt)]))
                
        # azimuth filter
        if 'min_az' in isprintForm:
            try:
                min_az = float(isprintForm['min_az'])
            except ValueError:
                min_az = float('nan')
            try:
                max_az = float(isprintForm['max_az'])
            except ValueError:
                max_az = float('nan')
            try:
                min_az2 = float(isprintForm['min_az2'])
            except ValueError:
                min_az2 = float('nan')
            try:
                max_az2 = float(isprintForm['max_az2'])
            except ValueError:
                max_az2 = float('nan')
            is_needed = False
            if not math.isnan(min_az):
                if min_az > -180.0:
                    is_needed = True
            if not math.isnan(max_az):
                if max_az < 180.0:
                    is_needed = True
            if is_needed:
                madFilters.append(madrigal.derivation.MadrigalFilter('azm', [(min_az, max_az), (min_az2, max_az2)]))
                
        # elevation filter
        if 'min_el' in isprintForm:
            try:
                min_el = float(isprintForm['min_el'])
            except ValueError:
                min_el = float('nan')
            try:
                max_el = float(isprintForm['max_el'])
            except ValueError:
                max_el = float('nan')
            try:
                min_el2 = float(isprintForm['min_el2'])
            except ValueError:
                min_el2 = float('nan')
            try:
                max_el2 = float(isprintForm['max_el2'])
            except ValueError:
                max_el2 = float('nan')
            is_needed = False
            if not math.isnan(min_el):
                if min_el > 0.0:
                    is_needed = True
            if not math.isnan(max_el):
                if max_el < 90.0:
                    is_needed = True
            if is_needed:
                madFilters.append(madrigal.derivation.MadrigalFilter('elm', [(min_el, max_el), (min_el2, max_el2)]))  
            
        # pulse length filter
        if 'min_pl' in isprintForm:
            file_min_pl = madFileObj.getMinPulseLength()
            file_max_pl = madFileObj.getMaxPulseLength()
            try:
                min_pl = float(isprintForm['min_pl'])
            except ValueError:
                min_pl = float('nan')
            try:
                max_pl = float(isprintForm['max_pl'])
            except ValueError:
                max_pl = float('nan')
            is_needed = False
            if not math.isnan(min_pl):
                if min_pl > file_min_pl + 1.0E-9:
                    is_needed = True
            if not math.isnan(max_pl):
                if max_pl < file_max_pl - 1.0E-9:
                    is_needed = True
            if is_needed:
                madFilters.append(madrigal.derivation.MadrigalFilter('pl', [(min_pl, max_pl)]))
        
        # free parameters
        for i in range(1, 4):
            parm_name = isprintForm['parm_%i' % (i)]
            parm_lower = isprintForm['parm_%i_lower' % (i)]
            parm_upper = isprintForm['parm_%i_upper' % (i)]
            if parm_name == 'None':
                continue
            if len(parm_lower) == 0 and len(parm_upper) == 0:
                continue
            # filter needed
            try:
                min_value = float(parm_lower)
            except ValueError:
                min_value = float('nan')
            try:
                max_value = float(parm_upper)
            except ValueError:
                max_value = float('nan')
            madFilters.append(madrigal.derivation.MadrigalFilter(parm_name, [(min_value, max_value)]))
            
        # create new temp file
        madrigal.isprint.Isprint(orgFilename, tmpFile, uniqueRequestedParms, madFilters,
                                 showHeaders=showHeaders, missing=missing, assumed=assumed, knownbad=knownbad)
        
        # log access
        self.logDataAccess(orgFilename, user_fullname, user_email, user_affiliation)
        
        return(tmpFile)
    
    
    def runMadrigalCalculatorFromForm(self, madCalculatorForm):
        """runMadrigalCalculatorFromForm returns the text output of madCalculator from the MadCalulatorForm
        
        Inputs:
            madCalculatorForm - the django form that encapsulates all information from madrigal_calculator web page.  
        """
        requestedParms = madCalculatorForm['parameters']
        requestedParms = ['gdlat', 'glon', 'gdalt'] + [str(parm) for parm in requestedParms]
        thisDT = madCalculatorForm['datetime']
        
        min_latitude = madCalculatorForm['min_latitude']
        max_latitude = madCalculatorForm['max_latitude']
        delta_latitude = madCalculatorForm['delta_latitude']
        
        min_longitude = madCalculatorForm['min_longitude']
        max_longitude = madCalculatorForm['max_longitude']
        delta_longitude = madCalculatorForm['delta_longitude']
        
        min_altitude = madCalculatorForm['min_altitude']
        max_altitude = madCalculatorForm['max_altitude']
        delta_altitude = madCalculatorForm['delta_altitude']
        
        latList = numpy.arange(min_latitude, max_latitude+0.001*delta_latitude, delta_latitude).tolist()
        lonList = numpy.arange(min_longitude, max_longitude+0.001*delta_longitude, delta_longitude).tolist()
        altList = numpy.arange(min_altitude, max_altitude+0.001*delta_altitude, delta_altitude).tolist()
        
        if 0 in (len(latList), len(lonList), len(altList)):
            raise ValueError('Got 0 length spatial range')
        
        output = os.path.join(tempfile.gettempdir(), 'tmp_%i.txt' % (random.randint(0,999999)))
        
        madrigal.isprint.MadCalculatorGrid(output, requestedParms, [thisDT], latList, lonList, altList)
        
        f = open(output)
        text = f.read()
        f.close()
        os.remove(output)
        return(text.strip())
    
    
    def runLookerFromForm(self, form):
        """runLookerFromForm returns the text output of looker from one of the looker forms
        
        Inputs:
            form - the django form that encapsulates all information from looker web page.  
        """
        looker_cmd = os.path.join(self._madDB.getMadroot(), 'bin/looker1')
        looker_options = int(form['looker_options'])
        if looker_options in (1,2):
            try:
                kinst = int(form['instruments'])
                if kinst == 0:
                    raise ValueError('')
                slatgd = self._instObj.getLatitude(kinst)
                slon = self._instObj.getLongitude(kinst)
                if slon > 180.0:
                    slon -= 360.0
                saltgd = self._instObj.getAltitude(kinst)
            except:
                slatgd = float(form['inst_lat'])
                slon = float(form['inst_lon'])
                saltgd = float(form['inst_alt'])
            try:
                year = float(form['year'])
            except:
                year = 2000.0
            argStr = ' %i ' + '%f ' * 13
            argStr = argStr % (looker_options, year, slatgd, slon, saltgd,
                               float(form['start_lat']), float(form['stop_lat']), float(form['step_lat']),
                               float(form['start_lon']), float(form['stop_lon']), float(form['step_lon']),
                               float(form['start_alt']), float(form['stop_alt']), float(form['step_alt']))
            looker_cmd += argStr
            try:
                text = subprocess.check_output(looker_cmd.split())
            except:
                raise IOError('Unable to run cmd <%s>' % (looker_cmd))
            if type(text) == bytes:
                text = text.decode('utf-8')
            return(text)
        
        elif looker_options in (3,):
            try:
                year = float(form['year'])
            except:
                year = 2000.0
            argStr = ' %i ' + '%f ' * 13
            argStr = argStr % (looker_options, year, 0.0, 0.0, 0.0,
                               float(form['start_lat']), float(form['stop_lat']), float(form['step_lat']),
                               float(form['start_lon']), float(form['stop_lon']), float(form['step_lon']),
                               float(form['start_alt']), float(form['stop_alt']), float(form['step_alt']))
            looker_cmd += argStr
            text = subprocess.check_output(looker_cmd.split())
            if type(text) == bytes:
                text = text.decode('utf-8')
            return(text)
        elif looker_options in (4,):
            try:
                kinst = int(form['instruments'])
                if kinst == 0:
                    raise ValueError('')
                slatgd = self._instObj.getLatitude(kinst)
                slon = self._instObj.getLongitude(kinst)
                if slon > 180.0:
                    slon -= 360.0
                saltgd = self._instObj.getAltitude(kinst)
            except:
                slatgd = float(form['inst_lat'])
                slon = float(form['inst_lon'])
                saltgd = float(form['inst_alt'])
            try:
                year = float(form['year'])
            except:
                year = 2000.0
            argStr = ' %i ' + '%f ' * 13
            argStr = argStr % (looker_options, year, slatgd, slon, saltgd,
                               float(form['start_az']), float(form['stop_az']), float(form['step_az']),
                               float(form['start_el']), float(form['stop_el']), float(form['step_el']),
                               float(form['start_range']), float(form['stop_range']), float(form['step_range']))
            looker_cmd += argStr
            text = subprocess.check_output(looker_cmd.split())
            if type(text) == bytes:
                text = text.decode('utf-8')
            return(text)
        elif looker_options in (5,6,7):
            try:
                kinst = int(form['instruments'])
                if kinst == 0:
                    raise ValueError('')
                slatgd = self._instObj.getLatitude(kinst)
                slon = self._instObj.getLongitude(kinst)
                if slon > 180.0:
                    slon -= 360.0
                saltgd = self._instObj.getAltitude(kinst)
            except:
                slatgd = float(form['inst_lat'])
                slon = float(form['inst_lon'])
                saltgd = float(form['inst_alt'])
            try:
                year = float(form['year'])
            except:
                year = 2000.0
            argStr = ' %i ' + '%f ' * 13
            if looker_options == 5:
                p1 = float(form['fl_az'])
                p2 = float(form['fl_el'])
                p3 = float(form['fl_range'])
            elif looker_options == 6:
                p1 = float(form['fl_lat'])
                p2 = float(form['fl_lon'])
                p3 = float(form['fl_alt'])
            elif looker_options == 7:
                p1 = float(form['fl_apex_lat'])
                p2 = float(form['fl_apex_lon'])
                p3 = 0.0
            argStr = argStr % (looker_options, year, slatgd, slon, saltgd,
                               p1, p2, p3,
                               float(form['start_alt']), float(form['stop_alt']), float(form['step_alt']),
                               0.0, 0.0, 0.0)
            looker_cmd += argStr
            text = subprocess.check_output(looker_cmd.split())
            if type(text) == bytes:
                text = text.decode('utf-8')
            return(text)
        elif looker_options in (8,):
            latList = numpy.arange(float(form['start_lat']), float(form['stop_lat']), float(form['step_lat']))
            latList = latList.tolist()
            # check for null list
            if len(latList) == 0 and abs(float(form['start_lat']) - float(form['stop_lat'])) < 1.0E-6:
                latList = [float(form['start_lat'])]
            lonList = numpy.arange(float(form['start_lon']), float(form['stop_lon']), float(form['step_lon']))
            lonList = lonList.tolist()
            # check for null list
            if len(lonList) == 0 and abs(float(form['start_lon']) - float(form['stop_lon'])) < 1.0E-6:
                lonList = [float(form['start_lon'])]
            altList = numpy.arange(float(form['start_alt']), float(form['stop_alt']), float(form['step_alt']))
            altList = altList.tolist()
            # check for null list
            if len(altList) == 0 and abs(float(form['start_alt']) - float(form['stop_alt'])) < 1.0E-6:
                altList = [float(form['start_alt'])]
            requestedParms = ['gdlat', 'glon', 'gdalt'] + [str(parm.lower()) for parm in form['pList']]
            dtList = [form['datetime']]
            output = os.path.join(tempfile.gettempdir(), 'tmp_%i.txt' % (random.randint(0,999999)))

            madrigal.isprint.MadCalculatorGrid(output, requestedParms, dtList, latList, lonList, altList)
            f = open(output)
            text = f.read()
            f.close()
            os.remove(output)
            if type(text) == bytes:
                text = text.decode('utf-8')
            return(text.strip())
            
        else:
            raise ValueError('Unknown looker_options %s' % (str(looker_options)))
        
            
        
        
    def cleanStage(self):
        """cleanStage removes all temp files more than 2 hours old from experiments/stage
        """
        stageDir = os.path.join(self._madDB.getMadroot(), 'experiments/stage')
        filesToTest = glob.glob(os.path.join(stageDir, '*'))
        now = datetime.datetime.now()
        cutoff = datetime.timedelta(hours=2)
        for fileToTest in filesToTest:
            try:
                mDT = datetime.datetime.fromtimestamp(os.path.getmtime(fileToTest))
            except:
                continue
            if now - mDT > cutoff:
                try:
                    os.remove(fileToTest)
                except:
                    pass # ignore problems
                
                
    def modifyBasename(self, basename):
        """modifyBasename adds _<num> to make sure basename unique
        """
        base, file_extension = os.path.splitext(basename)
        index = base.rfind('_')
        if index != -1:
            try:
                length = len(base[index+1:])
                version = int(base[index+1:])
                # in case of overflow
                length = max(length, len(str(version + 1)))
                format = '%%0%ii' % (length)
                return('%s_%s%s' % (base[:index], format % (version + 1), file_extension))
            except:
                pass
        return('%s_%i%s' % (base, 1, file_extension))
    
    
    def global_file_search(self, startDate, endDate, inst=None, kindat=None, 
                           seasonalStartDate=None, seasonalEndDate=None, 
                           includeNonDefault=False, expName=None, excludeExpName=None, 
                           fileDesc=None, returnCitation=False, dateList=None):
        """global_file_search supports commands that search the local madrigal site for files
        
        Used in global_download_service and global_group_id_service
        
        Inputs:
            startDate: start datetime to filter experiments before
            endDate: end datetime to filter experiments after 
            inst: a list of instrument codes or names. Default is None, meaning all instruments. 
                For names fnmatch will be used
            kindat: a list of kind of data codes or names. Default is None, meaning all kindats. 
                For names fnmatch will be used
            seasonalStartDate: in form MM/DD, rejects all days earlier in year. Default None
                implies 01/01
            seasonalEndDate: in form MM/DD, rejects all days later in year. Default None
                implies 12/31
            includeNonDefault: if True, include realtime files when there are no default. Default False
                implies only default files.
            expName: string - filter experiments by the experiment name.  fnmatch rules
                Default None is no filtering by experiment name.
            excludeExpName: string - exclude experiments by the experiment name.  fnmatch rules  
                Default None is no excluding experiments by experiment name.
            fileDesc: filter files using input file Description string via fnmatch. 
                Default None in no filtering by file name
            returnCitation: if True, return a list of file citations.  If False, default, return
                a list of full paths to the file
            dateList: a list of datetimes, to get experiments for 
                a list of discrete days. Must include startDate and endDate.
            
        """
        # first find instrument kinst list to search over, if not None
        if not inst is None:
            if type(inst) in (str, int):
                inst = [inst]
            insts = []  # will be filled with all kinst found
            instList = self._instObj.getInstrumentList()
            instDict = {}
            for instName, instMnem, kinst in instList:
                instDict[kinst] = instName
            for item in inst:
                try:
                    insts.append(int(item))
                except:
                    insts += self._searchDictByFnmatch(instDict, item)
            if len(insts) == 0:
                raise ValueError('No instruments found')
        else:
            insts = None
            
        # next find kindat list to search over, if not None
        if not kindat is None:
            if type(kindat) in (str, int):
                kindat = [kindat]
            kindats = []  # will be filled with all kindats found
            kindatList = self._madKindatObj.getKindatList()
            kindatDict = {}
            for kindatDesc, kindatCode in kindatList:
                kindatDict[kindatCode] = kindatDesc
            for item in kindat:
                try:
                    kindats.append(int(item))
                except:
                    kindats += self._searchDictByFnmatch(kindatDict, item)
            if len(kindats) == 0:
                raise ValueError('No kind of data codes found')
        else:
            kindats = None
        
        if not seasonalStartDate is None:
            startMonth = int(seasonalStartDate[:2])
            startDay = int(seasonalStartDate[-2:])
            
        if not seasonalEndDate is None:
            endMonth = int(seasonalEndDate[:2])
            endDay = int(seasonalEndDate[-2:])
            
        # get list of all experiment expDirs listed
        expDirs = []
        madExpObj = madrigal.metadata.MadrigalExperiment(self._madDB)
        for i in range(madExpObj.getExpCount()):
            sDTList = madExpObj.getExpStartDateTimeByPosition(i)[:6]
            eDTList = madExpObj.getExpEndDateTimeByPosition(i)[:6]
            sDT = datetime.datetime(*sDTList)
            eDT = datetime.datetime(*eDTList)
            if startDate > eDT:
                continue
            if endDate < sDT:
                continue
            if dateList:
                foundDate = False
                for thisDate in dateList:
                    if (sDT.date() == thisDate) or (eDT.date() == thisDate):
                        foundDate = True
                        break
                if not foundDate:
                    continue

            # instrument filter
            if not insts is None:
                if madExpObj.getKinstByPosition(i) not in insts:
                    continue
            # seasonal start date filter
            if not seasonalStartDate is None:
                if sDT.month < startMonth:
                    continue
                if sDT.month == startMonth and sDT.day < startDay:
                    continue
            # seasonal end date filter
            if not seasonalEndDate is None:
                if eDT.month > endMonth:
                    continue
                if eDT.month == endMonth and eDT.day > endDay:
                    continue
            # exp name filter
            if not expName is None:
                thisExpName = madExpObj.getExpNameByPosition(i)
                if not fnmatch.fnmatch(thisExpName.lower(), expName.lower()):
                    continue
            # exclude exp name filter
            if not excludeExpName is None:
                thisExpName = madExpObj.getExpNameByPosition(i)
                if fnmatch.fnmatch(thisExpName.lower(), excludeExpName.lower()):
                    continue
            # made it through all filters
            expDirs.append(madExpObj.getExpDirByPosition(i))
            
        # finally, collect all filenames or citable urls that pass the file
        # level filters
        retList = []
        for expDir in expDirs:
            if not os.access(os.path.join(expDir, 'fileTab.txt'), os.R_OK):
                continue
            madFileObj = madrigal.metadata.MadrigalMetaFile(self._madDB,
                                                            os.path.join(expDir, 'fileTab.txt'))
            for i in range(madFileObj.getFileCount()):
                if includeNonDefault:
                    defaultFound = False
                    rtList = [] 
                # kindat
                if not kindat is None:
                    if madFileObj.getKindatByPosition(i) not in kindats:
                        continue
                # fileDesc
                if not fileDesc is None:
                    thisDesc = madFileObj.getStatusByPosition(i)
                    if not fnmatch.fnmatch(thisDesc.lower(), fileDesc.lower()):
                        continue
                # final filter - category
                category = madFileObj.getCategoryByPosition(i)
                if not includeNonDefault and category != 1:
                    continue
                if includeNonDefault:
                    if not defaultFound and category == 4:
                        # add temporarily to rtList
                        if returnCitation:
                            rtList.append(madFileObj.getFileDOIUrlByPosition(i))
                        else:
                            rtList.append(os.path.join(expDir,
                                                       madFileObj.getFilenameByPosition(i)))
                        continue
                    elif category != 1:
                        continue
                # accepted
                if includeNonDefault:
                    defaultFound = True
                if returnCitation:
                    retList.append(madFileObj.getFileDOIUrlByPosition(i))
                else:
                    retList.append(os.path.join(expDir, madFileObj.getFilenameByPosition(i)))
                    
            # check for no default file
            if includeNonDefault:
                if not defaultFound and len(rtList) > 0:
                    retList += rtList
                    
        return(retList) 
            
        
        
        
    def _searchDictByFnmatch(self, dict, searchStr):
        """_searchDictByFnmatch is a helper method to support global_file_search.  
        
        Inputs:
            dict - a dictionary whose keys are unique values (integers or strings), and
                whose values are strings to be searched over using searchStr
            searchStr - a string in the form used by fnmatch to do case-insensitive
                matching.  
                
        Returns: a list of keys in dict where the string value matched.  Empty list
            if not matches
        """
        retList = []
        for key in dict:
            if fnmatch.fnmatch(dict[key].lower(), searchStr.lower()):
                retList.append(key)
                
        return(retList)
            
            
        
            
            
    def _getDaynoFilter(self, seasonalStartDate, seasonalEndDate):
        """_getDaynoFilter returns a filter str in the form dayno,<lower>,<upper>
        
        Inputs:
            seasonalStartDate - a string in form 'MM/DD'.  Assumes non-leap year.
                Empty string means no filtering by seasonal start date.
            seasonalStartDate - a string in form 'MM/DD'.  Assumes non-leap year.
                Empty string means no filtering by seasonal end date.
        """
        startDayno = ''
        endDayno = ''
        if len(seasonalStartDate):
            startItems = seasonalStartDate.split('/')
            startDT = datetime.datetime(1958, int(startItems[0]),  int(startItems[1]))
            startDayno = int(startDT.strftime('%j'))
        if len(seasonalEndDate):
            endItems = seasonalEndDate.split('/')
            endDT = datetime.datetime(1958, int(endItems[0]),  int(endItems[1]))
            endDayno = int(endDT.strftime('%j'))
        return('dayno,%i,%i' % (startDayno, endDayno))


    def _getLock(self, filename):
        """_getLock is a private helper function that provides exclusive access to filename via a locking file.

        Inputs: filename = the file that exclusive access is required to.
        
        Returns: None

        Affects: Writes file filename + .LCK as a lock mechanism

        Exceptions: MadrigalError thrown if unable to write lock file

        Notes: Will sleep for 1 second at a time, for a maximum of _MaxSleep seconds (presently 10)
        if the file is not modified. After each second, it will check for the lock file to be removed
        or modified. If it was modified, it resets the count to 0 sec and starts counting again. After
        _MaxSleep counts it then assumes lock file is orphaned and returns.  Orphaned file will be
        removed when dropLock is called.
        """
        gotLock = 0
        numTries = 0
        modificationTime = 0
        
        while (not gotLock):

            try:
                file = os.open(filename + '.LCK', os.O_RDWR | os.O_CREAT | os.O_EXCL)
                os.close(file)
                gotLock = 1

            except OSError:
                # error 17 is "File exists"
                #(errno, strerror) = xxx_todo_changeme.args
                # error 17 is "File exists"
                #if errno != 17:
                    #raise madrigal.admin.MadrigalError("Unable to open " + filename + ".LCK as locking file ", None)
                # get modification time - may throw an error if file has disappearred
                try:
                    newModTime = (os.stat(filename + '.LCK')).st_mtime
                except:
                    #file has disappeared, no need to sleep
                    continue

                # if the lock file has been modified (or if this is the first time through) set numTries = 0
                if newModTime > modificationTime:
                    modificationTime = newModTime
                    numTries = 0
                    
                time.sleep(1)
                
            numTries = numTries + 1

            if numTries > self._MaxSleep:
                return

       
    def _dropLock(self, filename):
        """_dropLock is a private helper function that drops exclusive access to filename via a locking file.

        Inputs: filename = the file that exclusive access is required to.
        
        Returns: None

        Affects: Removes file filename + .LCK as a lock mechanism

        Exceptions: None.
        """
        try:
            os.remove(filename + '.LCK')

        except IOError:
            return


class MadrigalWebFormat:
    """MadrigalWebFormat defines the format of an web interface.

    Information about how a web page is formatted is stored in this class.  In particular,
    the possible derived parameters to display for a given format (such as Short or
    Comprehensive) are set in this class.  Edit this class to create new formats or
    modify existing ones.

    Non-standard Python modules used:
    None

    No exceptions thrown

    Change history:

    Written by "Bill Rideout":mailto:wrideout@haystack.mit.edu  Oct. 29, 2001
    """

    # constants

    # Edit this data to change which parameters to display
    # or to add new formats
    #
    #                   Format          Parameters      
    #                   ------          ----------  
    _privateDict =  {'Comprehensive':  [   'year',
                                            'month',
                                            'day',
					                        'bmonth',
					                        'bday',
                                            'hour',
                                            'min',
                                            'sec',
                                            'md',
                                            'dayno',
                                            'bhm',
                                            'bhhmmss',
                                            'ehhmmss',
                                            'uth',
                                            'b_uth',
                                            'ut',
                                            'ut1_unix',
                                            'ut2_unix',
                                            'beg_ut',
                                            'slt',
                                            'sltc',
                                            'fyear',
                                            'sunrise_hour',
                                            'sunset_hour',
                                            'conj_sunrise_h',
                                            'conj_sunset_h',
                                            'aplt',
                                            'julian_date',
                                            'gdalt',
                                            'range',
                                            'resl',
                                            'azm',
                                            'az1',
                                            'az2',
                                            'elm',
                                            'el1',
                                            'el2',
                                            'gdlat',
                                            'glon',
                                            'szen',
                                            'szenc',
                                            'sdwht',
                                            'beamid',
                                            'bn',
                                            'be',
                                            'bd',
                                            'magh',
                                            'magd',
                                            'magzu',
                                            'bmag',
                                            'bdec',
                                            'binc',
                                            'lshell',
                                            'diplat',
                                            'invlat',
                                            'aplat',
                                            'aplon',
                                            'e_reg_s_lat',
                                            'e_reg_s_lon',
                                            'e_reg_s_sdwht',
                                            'e_reg_n_lat',
                                            'e_reg_n_lon',
                                            'e_reg_n_sdwht',
                                            'magconjlat',
                                            'magconjlon',
                                            'magconjsdwht',
                                            'mlt',
                                            'tsyg_eq_xgsm',
                                            'tsyg_eq_ygsm',
                                            'tsyg_eq_xgse',
                                            'tsyg_eq_ygse',
                                            'aacgm_lat',
                                            'aacgm_long',
                                            'aspect',
                                            'cxr',
                                            'cyr',
                                            'czr',
                                            'pl',
                                            'snp3',
                                            'chisq',
                                            'gfit',
                                            'mhdqc1',
                                            'systmp',
                                            'systmi',
                                            'power',
                                            'tfreq',
                                            'popl',
                                            'ne',
                                            'nel',
                                            'ti',
                                            'te',
                                            'tr',
                                            'vo',
                                            'ph+',
                                            'pm',
                                            'co',
                                            'vdopp',
                                            'dvdopp',
                                            'dco',
                                            'dpm',
                                            'dph+',
                                            'dvo',
                                            'dtr',
                                            'dte',
                                            'dti',
                                            'dpopl',
                                            'dne',
                                            'ne_model',
                                            'nel_model',
                                            'te_model',
                                            'ti_model',
                                            'vo_model',
                                            'hmax_model',
                                            'nmax_model',
                                            'ne_modeldiff',
                                            'nel_modeldiff',
                                            'te_modeldiff',
                                            'ti_modeldiff',
                                            'vo_modeldiff',
                                            'tn',
                                            'tnm',
                                            'tinfm',
                                            'mol',
                                            'nn2l',
                                            'no2l',
                                            'nol',
                                            'narl',
                                            'nhel',
                                            'nhl',
                                            'nn4sl',
                                            'fa',
                                            'pnrmd',
                                            'pnrmdi',
                                            'ut1',
                                            'ut2',
                                            'dut21',
                                            'kinst',
                                            'recno',
                                            'kindat',
                                            'fof2',
                                            'dfa',
                                            'dst',
                                            'kp',
                                            'ap',
                                            'ap3',
                                            'f10.7',
                                            'fbar',
                                            'pdcon',
                                            'dpdcon',
                                            'hlcon',
                                            'dhlcon',
                                            'ne_iri',
                                            'nel_iri',
                                            'tn_iri',
                                            'te_iri',
                                            'ti_iri',
                                            'po+_iri',
                                            'pno+_iri',
                                            'po2+_iri',
                                            'phe+_iri',
                                            'ph+_iri',
                                            'pn+_iri',
                                            'bxgsm',
                                            'bygsm',
                                            'bzgsm',
                                            'bimf',
                                            'bxgse',
                                            'bygse',
                                            'bzgse',
                                            'swden',
                                            'swspd',
                                            'swq'],
                      'Short':          [   'year',
                                            'md',
                                            'dayno',
                                            'uth',
                                            'b_uth',
                                            'ut',
                                            'beg_ut',
                                            'lt',
                                            'aplt',
                                            'jdayno',
                                            'gdalt',
                                            'range',
                                            'azm',
                                            'az1',
                                            'az2',
                                            'elm',
                                            'el1',
                                            'el2',
                                            'gdlat',
                                            'glon',
                                            'popl',
                                            'nel',
                                            'ti',
                                            'te',
                                            'tr',
                                            'vo',
                                            'ph+',
                                            'pm',
                                            'co',
                                            'vdopp',
                                            'dvdopp',
                                            'dco',
                                            'dpm',
                                            'dph+',
                                            'dvo',
                                            'dtr',
                                            'dte',
                                            'dti',
                                            'dpopl',
                                            'dne',
                                            'kp',
                                            'ap',
                                            'ap3',
                                            'f10.7',
                                            'fbar']}

    def getFormat(self, formatName):
        return self._privateDict[formatName]



