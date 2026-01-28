"""userData is responsible for interfacing to all persisted user data on the madrigal web site.

This module is meant to hide the storage mechnaism of user data on the madrigal web site, so that
the present format (xml files) can be changed by only changing this module.  The data stored at the
moment consists of user login information, and directories (private and public) of stored filters,
where a filter is all information that determines the output of an isprint display.

This modules requires that the non-standard python module PyXML be installed (this module may become
standard in a future release of python).  See the python XML SIG for this module.

$Id: userData.py 7242 2020-10-05 17:59:38Z brideout $
"""
# standard python imports
import os
import string
import time
import stat
import traceback
import shutil
import xml.dom.minidom
import xml.sax.handler

# Madrigal imports
import madrigal.metadata

# third party imports
import purecrypt as crypt


class MadrigalUserData:
    """MadrigalUserData is an object that provides access to all user data.

    The object MadrigalUserData is an object that provides read and write access to
    all persisted user information on the Madrigal web site.  For the moment this data
    consists of which instruments and experiments the user is registered with.

    Change history:

    Written by "Bill Rideout":mailto:wrideout@haystack.mit.edu  Dec. 11, 2001

    """

    #constants
    _userXMLDir   = "userdata"
    _userXMLFile  = "users.xml"
    _userXMLFileTemplate = "users.xml.template"
    _userExpFile = 'regExp.txt'  # contains list of registered experiments
    _userInstFile = 'regInst.txt' # contains list of registered instruments# maximum number of seconds to wait for a lock
    _MaxSleep     = 10
    # 2 char string to use in crypt
    # Changing this will cause all stored passwords to fail
    _cryptStr     = 'md'
    

    def __init__(self, madDB = None):
        """__init__ initializes MadrigalUserData by reading from MadridalDB..

        Inputs: Existing MadrigalDB object, by default = None.
        
        Returns: void

        Affects: Initializes self._metaDir.

        Exceptions: None.
        """

        # get metadata dir
        if madDB == None:
            thisMadDB = madrigal.metadata.MadrigalDB()
        else:
            thisMadDB = madDB

        self._metaDir = thisMadDB.getMetadataDir()
        
        # check that users.xml exists, if not, copy users.xml.template
        if not os.path.isfile(self._metaDir + '/' + self._userXMLDir + '/' + self._userXMLFile):
            shutil.copyfile(self._metaDir + '/' + self._userXMLDir + '/' + self._userXMLFileTemplate,
                            self._metaDir + '/' + self._userXMLDir + '/' + self._userXMLFile)

    
    
    def getRegisteredDict(self):
        """will return a dictionary with key  
            + email, and value = tuple of all registered experiments for that  
            email.
            
            This data will be stored in a text file: MADROOT/metadata/userdata/ 
            regExp.txt.  The format will be two space delimited columns: email  
            experimentString.
        """
        filename = os.path.join(self._metaDir, self._userXMLDir, self._userExpFile)
        
        retDict = {}

        try:
            f = open(filename)
        except IOError:
            return(retDict)
        
        lines = f.readlines()
        for line in lines:
            items = line.split()
            if len(items) != 2:
                continue
            try:
                retDict[items[0]].append(items[1])
            except KeyError:
                retDict[items[0]] = [items[1]]
                
        return(retDict)
    
    
    def getRegisteredExperiments(self, email):
        """getRegisteredExperiments will return a list of  
            experiments as strings.  For example, getRegisteredExperiments('brideout at haystack.mit.edu') 
            might return ['experiments/2010/mlh/18jan10', 'experiments/2010/mlh/19jan10', 
            'experiments/2010/mlh/20jan10'].  If the user has no  
            registered experiments, it will return an empty list.
            
        Inputs: user email
        """
        expDict = self.getRegisteredDict()
        try:
            return(expDict[email])
        except KeyError:
            return(())
        
        
    def getRegisteredUsers(self, experimentString):
        """ getRegisteredUsers will return a list  
            of users register for a given experiment as strings.  For example,  
            getRegisteredUsers('experiments/2010/mlh/18jan10') might return ['brideout at haystack.mit.edu ', 
            'miguel.urco at jro.igp.gob.pe'].  If the experiment has no registered  
            users, it will return an empty list
        """
        retList = []
        if experimentString[-1] == '/':
            experimentString = experimentString[:-1]
        expDict = self.getRegisteredDict()
        for key in list(expDict.keys()):
            for item in expDict[key]:
                if item == experimentString:
                    if key not in retList:
                        retList.append(key)
                        
        return(retList)
    
    
    def registerExperiment(self, email, experimentString):
        """registerExperiment method will  
            register an experiment for a given email.  For example,  
            registerExperiment('brideout at haystack.mit.edu', 'experiments/2010/mlh/ 
            18jan10') would register an experiment.  If the experiment is already  
            registed, it will not raise an error; it will simply do nothing.
            
        Affects: This new data will be stored in a text file: MADROOT/metadata/userdata/ 
            regExp.txt.  The format will be two space delimited columns: email  
            experimentString.
        """
        # check if already registered
        expDict = self.getRegisteredDict()
        if experimentString[-1] == '/':
            experimentString = experimentString[:-1]
        try:
            expList = expDict[email]
            if experimentString in expList:
                return
        except KeyError:
            pass
        
        # not registered
        filename = os.path.join(self._metaDir, self._userXMLDir, self._userExpFile)
        self._getLock(filename)
        # make sure up to date
        expDict = self.getRegisteredDict()
        try:
            expDict[email].append(experimentString)
        except KeyError:
            expDict[email] = [experimentString]
        try:
            f = open(filename, 'w')
        except:
            self._dropLock(filename)
            raise
        
        keys = list(expDict.keys())
        keys.sort()
        for key in keys:
            for item in expDict[key]:
                f.write('%s %s\n' % (key, item))
        f.close()
        
        self._dropLock(filename)
        
        
    def unregisterExperiment(self, email, experimentString):
        """unregisterExperiment method will  
            unregister an experiment for a given email.  For example,  
            unregisterExperiment('brideout at haystack.mit.edu', 'experiments/2010/ 
            mlh/18jan10') would unregister an experiment.  If the experiment is  
            not registed, it will not raise an error; it will simply do nothing.
            
        Affects: This data will be removed from a text file: MADROOT/metadata/userdata/ 
            regExp.txt.  The format will be two space delimited columns: email  
            experimentString.
        """
        # check if already registered
        found = False
        expDict = self.getRegisteredDict()
        if experimentString[-1] == '/':
            experimentString = experimentString[:-1]
        try:
            expList = expDict[email]
            if experimentString in expList:
                found = True
        except KeyError:
            pass
        
        if not found:
            return
        
        # is registered
        filename = os.path.join(self._metaDir, self._userXMLDir, self._userExpFile)
        self._getLock(filename)
        # make sure up to date
        expDict = self.getRegisteredDict()
        regExp = expDict[email]
        regExp.remove(experimentString)
        expDict[email] = regExp
        try:
            f = open(filename, 'w')
        except:
            self._dropLock(filename)
            raise
        
        keys = list(expDict.keys())
        keys.sort()
        for key in keys:
            for item in expDict[key]:
                f.write('%s %s\n' % (key, item))
        f.close()
        
        self._dropLock(filename)
        
        
        
    def getRegisteredInstDict(self):
        """will return a dictionary with key  
            = email, and value = tuple of all registered instrument codes (int) for that  
            email.
            
            This data will be stored in a text file: MADROOT/metadata/userdata/ 
            regInst.txt.  The format will be two space delimited columns: email  
            instrument code (int).
        """
        filename = os.path.join(self._metaDir, self._userXMLDir, self._userInstFile)
        
        retDict = {}

        try:
            f = open(filename)
        except IOError:
            return(retDict)
        
        lines = f.readlines()
        for line in lines:
            items = line.split()
            if len(items) != 2:
                continue
            try:
                retDict[items[0]].append(int(items[1]))
            except KeyError:
                retDict[items[0]] = [int(items[1])]
                
        return(retDict)
    
    
    def getRegisteredInstruments(self, email):
        """getRegisteredInstruments will return a list of  
            instruments as ints.  For example, getRegisteredInstruments('brideout at haystack.mit.edu') 
            might return [30, 31, 10].  If the user has no  
            registered instruments, it will return an empty list.
            
        Inputs: user email
        """
        instDict = self.getRegisteredInstDict()
        try:
            return(instDict[email])
        except KeyError:
            return(())
        
        
    def getRegisteredInstUsers(self, kinst):
        """ getRegisteredInstUsers will return a list  
            of users registered for a given instrument code (kinst) as strings.  For example,  
            getRegisteredInstUsers(30) might return ['brideout at haystack.mit.edu ', 
            'miguel.urco at jro.igp.gob.pe'].  If the instrument has no registered  
            users, it will return an empty list
        """
        retList = []
        instDict = self.getRegisteredInstDict()
        for key in list(instDict.keys()):
            for item in instDict[key]:
                if item == kinst:
                    if key not in retList:
                        retList.append(key)
                        
        return(retList)
    
    
    def registerInstrument(self, email, kinst):
        """registerInstrument method will  
            register an instrument for a given email.  For example,  
            registerInstrument('brideout at haystack.mit.edu', 30) would 
            register an instrument.  If the instrument is already  
            registed, it will not raise an error; it will simply do nothing.
            
        Affects: This new data will be stored in a text file: MADROOT/metadata/userdata/ 
            regInst.txt.  The format will be two space delimited columns: email  
            kinst.
        """
        # check if already registered
        instDict = self.getRegisteredInstDict()
        try:
            instList = instDict[email]
            if kinst in instList:
                return
        except KeyError:
            pass
        
        # not registered
        filename = os.path.join(self._metaDir, self._userXMLDir, self._userInstFile)
        self._getLock(filename)
        # make sure up to date
        instDict = self.getRegisteredInstDict()
        try:
            instDict[email].append(kinst)
        except KeyError:
            instDict[email] = [kinst]
        try:
            f = open(filename, 'w')
        except:
            self._dropLock(filename)
            raise
        
        keys = list(instDict.keys())
        keys.sort()
        for key in keys:
            for item in instDict[key]:
                f.write('%s %s\n' % (key, str(item)))
        f.close()
        
        self._dropLock(filename)
        
        
    def unregisterInstrument(self, email, kinst):
        """unregisterInstrument method will  
            unregister an instrument for a given email.  For example,  
            unregisterInstrument('brideout at haystack.mit.edu', 30) 
            would unregister an instrument.  If the instrument is  
            not registed, it will not raise an error; it will simply do nothing.
            
        Affects: This data will be removed from a text file: MADROOT/metadata/userdata/ 
            regInst.txt.  The format will be two space delimited columns: email  
            kinst.
        """
        # check if already registered
        found = False
        instDict = self.getRegisteredInstDict()
        try:
            instList = instDict[email]
            if kinst in instList:
                found = True
        except KeyError:
            pass
        
        if not found:
            return
        
        # is registered
        filename = os.path.join(self._metaDir, self._userXMLDir, self._userInstFile)
        self._getLock(filename)
        # make sure up to date
        instDict = self.getRegisteredInstDict()
        regInst = instDict[email]
        regInst.remove(kinst)
        instDict[email] = regInst
        try:
            f = open(filename, 'w')
        except:
            self._dropLock(filename)
            raise
        
        keys = list(instDict.keys())
        keys.sort()
        for key in keys:
            for item in instDict[key]:
                f.write('%s %s\n' % (key, item))
        f.close()
        
        self._dropLock(filename)
        
        
    def getUsersList(self):
        """getUsersList returns a list of user names/encrypted passwords that already exist.

        Inputs: none.
        
        Returns: a list of user names/passwords.  Each item in the returned list is itself a
        list with two strings: 1) username, and 2) encrypted password.

        Usage example:

            import madrigal.ui.userData

            test = madrigal.ui.userData.MadrigalUserData()

            userlist = test.getUsersList()

            for user in userlist:

                print 'User name is ' + user[0] + ' and encrypted password is ' + user[1]

        Affects: None

        Exceptions: none
        """
        
        # update userList
        self._loadUserData()
        
        return self._userList


    def userExists(self, username):
        """userExists returns 1 if username (case insensitive) exists, 0 otherwise.

        Inputs: username string.
        
        Returns: 1 if username (case insensitive) exists, 0 otherwise.

        Affects: None

        Exceptions: none
        """

        # update userList
        self._loadUserData()

        nameLowCase = username.lower().strip()
        
        for name in self._userList:
            if nameLowCase == name[0].lower().strip():
                return 1

        #not found
        return 0


    def verifyUser(self, username, password):
        """verifyUser returns 1 if username, password okay, 0 otherwise.

        Inputs: username string, password string.
        
        Returns: 1 if username, password okay, 0 otherwise.

        Affects: None

        Exceptions: none
        """

        # update userList
        self._loadUserData()

        nameLowCase = username.lower().strip()
        
        for name in self._userList:
            if nameLowCase == name[0].lower().strip():
                # username found, now encrypt password
                pwdEncrypt = crypt.crypt(password, self._cryptStr)
                # verify password
                if pwdEncrypt == name[1]:
                    return 1
                else:
                    # wrong password
                    return 0

        # username not found
        return 0


    def addUser(self, username, password):
        """addUser returns 1 if user added successfully, error string otherwise.

        Inputs: username string, password string (password is not yet encrypted).
        
        Returns: 1 if user added successfully, error string otherwise.   

        Affects: Adds new user to self._userList, writes new empty <username>.xml file
        username is always converted and stored as lower case, so its case insensitive.

        Exceptions: MadrigalError thrown if unable to write to user xml file

        Notes:  uses getLock and dropLock to insure exclusive access to user file
        """

        filename = self._metaDir + '/' + self._userXMLDir + '/' + self._userXMLFile

        if username == None:
            return "Cannot create a user with null user name."
        
        # store all usernames as lowercase
        username = username.lower().strip()

        if len(username) == 0:
            return "Cannot create a user with blank user name."

        # lock out any method that writes to file
        self._getLock(filename)
        
        # user data loaded by userExists

        if self.userExists(username):
            # done with user file - allow access to other writing calls
            self._dropLock(filename)
            return 'User name ' + username + ' already exists.'

        if not self._isValidFileName(username):
            # done with user file - allow access to other writing calls
            self._dropLock(filename)
            return 'Username ' + username + ' contains illegal characters.'


        #encrypt password
        pwdEncrypt = crypt.crypt(password, self._cryptStr)

        # create dom
        userDoc = xml.dom.minidom.parse(filename)

        #get root element
        docRoot = userDoc.documentElement

        # create new user element
        newUserElem = userDoc.createElementNS(None, 'user')

        # now create new name element under newUserElem
        newUsernameElem = userDoc.createElementNS(None, 'name')

        # Create a text node
        newUsernameText = userDoc.createTextNode(username)

        # append text node to newUsernameElem
        newUsernameElem.appendChild(newUsernameText)

        # append name node to user node
        newUserElem.appendChild(newUsernameElem)

        #now create new password element under newUserElem
        newPasswordElem = userDoc.createElementNS(None, 'password')

        #Create a text node
        newPasswordText = userDoc.createTextNode(pwdEncrypt)

        # append text node to newPasswordElem
        newPasswordElem.appendChild(newPasswordText)

        # append password node to user node
        newUserElem.appendChild(newPasswordElem)

        #Add the new user element to the document element
        docRoot.appendChild(newUserElem)

        #output result
        outfp = open(filename, 'w')
        userDoc.writexml(outfp)
        outfp.write("\n")
        outfp.close()

        # done with user file - allow access to other writing calls
        self._dropLock(filename)

        # create new file <username>.xml
        outfp = open(self._metaDir + '/' + self._userXMLDir + '/' + username + '.xml', 'w')
        outfp.write('<?xml version=\'1.0\'?>\n')
        outfp.write('<userInfo>\n')
        outfp.write('</userInfo>\n')
        outfp.close()
                     

        return 1


    def changePassword(self, username, password):
        """changePassword returns 1 if user password changed successfully, error string otherwise.

        Inputs: username string, password string (password is not yet encrypted).
        
        Returns: 1 if password changed successfully, error string otherwise.

        Affects: Modifies password in self._userList, writes new user.xml file

        Exceptions: MadrigalError thrown if unable to write user xml file
        """

        username = username.lower().strip()

        filename = self._metaDir + '/' + self._userXMLDir + '/' + self._userXMLFile

        # lock out any method that writes to file
        self._getLock(filename)

        # user data loaded by userExists

        #make username lower, without white space
        username = username.lower().strip()

        if not self.userExists(username):
            return 'User ' + username + ' does not exist.'

        #encrypt password
        pwdEncrypt = crypt.crypt(password, self._cryptStr)

        # open dom
        userDoc = xml.dom.minidom.parse(filename)

        #now create new password element to replace old
        newPasswordElem = userDoc.createElementNS(None, 'password')

        #Create a text node
        newPasswordText = userDoc.createTextNode(pwdEncrypt)

        # append text node to newPasswordElem
        newPasswordElem.appendChild(newPasswordText)

        # get all user elements
        userElemList = userDoc.getElementsByTagName("user")

        # loop through each user element
        for user in userElemList:
            thisUserNameEl = user.getElementsByTagName('name')[0]
            if username == self._getText(thisUserNameEl.childNodes):
                # modify password
                thisPasswordEl = user.getElementsByTagName('password')[0]
                user.replaceChild(newPasswordElem, thisPasswordEl)

        #output result
        outfp = open(self._metaDir + '/' + self._userXMLDir + '/' + self._userXMLFile, 'w')
        userDoc.writexml(outfp)
        outfp.write("\n")
        outfp.close()

        # done with user file - allow access to other writing calls
        self._dropLock(filename)
                     
        return 1
        
        
        
    def _loadUserData(self):
        """_loadUserData is a private helper function that reads in user information from an xml file.

        Inputs: None.
        
        Returns: void

        Affects: Populates self._userList.

        Exceptions: MadrigalError thrown  if problem parsing users.xml.

        Depends on: Existance of file in metadata dir self._userXMLDir + '/' + self._userXMLFile (now userdata/user.xml)

        This file must be of the form of the following format:

            <?xml version='1.0'?>
            
            <users>
            
              <user>
              
                <name>brideout</name>
                
                <password>briWy6v1L.z1E</password>
                
              </user>
              
              possibly more users...
              
            </users>

        The password is stored encrypted by crypt.crypt(password, self._cryptStr).  Implemented via xml.dom, since it is
        only a short file, but for higher speed (and more complex code) could be implemented with sax since read only.
        
        """

        filename = self._metaDir + '/' + self._userXMLDir + '/' + self._userXMLFile

        #check that user xml file exists, if not throw error
        if not os.access(filename, os.F_OK):
            raise madrigal.admin.MadrigalError("Unable to open " + filename, None)
        

        #get list of user names
        userDoc = xml.dom.minidom.parse(filename)

        #userDoc is root element of users.xml

        self._userList = []

        # get all user tags
        userElemList = userDoc.getElementsByTagName("user")
        
        for user in userElemList:
            # get name from user list
            nameEl = user.getElementsByTagName("name")[0]

            # get text node, convert from unicode to ascii
            for elem in nameEl.childNodes:
                if elem.nodeType == elem.TEXT_NODE:
                   tempName = elem.data

            # get encrypted password from user list
            nameEl = user.getElementsByTagName("password")[0]

            # get text node, convert from unicode to ascii
            for elem in nameEl.childNodes:
                if elem.nodeType == elem.TEXT_NODE:
                    tempPassword = elem.data

            #append this user's information to user list
            self._userList.append([tempName, tempPassword])
            
            
            
    def _isValidFileName(self, name):
        """_isValidFileName is a private helper function that validates that the string name does not contain excluded characters.
        
        Inputs: name - the string to be validated.
        
        Returns: 1 if all characters are allowed, 0 otherwise.  Valid if the following characters are not found in the
        string after leading and trailing whitespace is removed: [' ', '/', '<', '>', '\']

        Affects: None

        Exceptions: None.
        """

        name = name.strip()

        invalidChars = [' ', '/', '<', '>', '\\']

        # check if any invalid characters found in name
        for char in invalidChars:
            if -1 != name.find(char):
                # invalid char found
                return 0

        return 1
            
            
    
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

            except OSError as xxx_todo_changeme:
                # error 17 is "File exists"
                (errno, strerror) = xxx_todo_changeme.args
                # error 17 is "File exists"
                if errno != 17:
                    raise madrigal.admin.MadrigalError("Unable to open " + filename + ".LCK as locking file ", None)
                # get modification time - may throw an error if file has disappearred
                try:
                    newModTime = os.stat(filename + '.LCK')[stat.ST_MTIME]
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

    
