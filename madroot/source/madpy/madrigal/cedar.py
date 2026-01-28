"""cedar is the module that allows the creation and editing of Cedar files.

With Madrigal 3.0, this module was rewritten to work with the power of the hdf5 I/O library.  Editing a file
now never needs to load the file into memory.  Instead, only the slice needing modification is read in.

Any input file must now be an Hdf5 one.  However, this module can output a file in any format.

The underlying data structure is a h5py dataset object, which is read from the hdf5 file under the group "Data" and the
dataset name "Table Layout".  Data not yet written in may also be stored in a numpy recarray with the
same dtype.

With Madrigal 2.X, this module abstracts away many of the details of the Cedar file format, which may change in the future,
and instead simply follows the Cedar data model (Prolog-1d parms-2d parms).  For example, all values are accessed and set via doubles, so
users do not need to deal with scale factors, "additional increment" parameters, etc.  The old Cedar file format had
limited dynamic range, so for now an exception is raised if any value would violate this limited range.  Furthermore,
the Cedar data model defines time in the prolog.  Unfortunately, time may also be set in the data itself, leading
to the possibility of inconsistent data.  This module will issue warnings in that case.

With Madrigal 3.0, this module  is built on top of the h5py hdf5 interface

$Id: cedar.py 7655 2024-06-27 20:20:49Z kcariglia $
"""
# standard python imports
import os, os.path, sys
import array
import types
import time
import datetime
import traceback
import itertools
import re
import warnings
import subprocess
import shlex
import shutil
import copy
import collections

# third party imports
import numpy
import numpy.lib.recfunctions
import netCDF4
import h5py

# Millstone imports
import madrigal.metadata
import madrigal.data
import madrigal.admin

# cedar special values
missing  = numpy.nan
assumed  = -1.0
knownbad = -2.0
timeParms = 30 # any Cedar parameter below this number is a time parameter that conflicts with prolog

def getLowerCaseList(l):
    """getLowerCaseList returns a new list that is all lowercase given an input list
    that may have upper case strings
    """
    return([s.lower() for s in l])

def fixBinaryString(s):
    """fixBinaryString is a helper function to remove b'**' around output strings.  s is a re.match
    object that matched the pattern "b\'[^\']\'".  It returns the string with the first two characters
    and the last character removed.
    """
    if s is None:
        return('')
    else:
        return(s.group(0)[2:-1])


def parseArraySplittingParms(hdf5Filename):
        """parseArraySplittingParms returns a (possibly empty) list of parameter mnemonic used to split
        the array layout for a Madrigal Hdf5 file
        
        Input: hdf5Filename - Madrigal Hdf5 filename
        
        Raise IOError if not a valid Madrigal Hdf5 file
        """
        with h5py.File(hdf5Filename, 'r') as f:
            try:
                dataGroup = f['Data']
            except:
                raise IOError('Hdf5 file %s does not have required top level Data group' % (hdf5Filename))
            retList = []
            if 'Array Layout' not in list(dataGroup.keys()):
                return(retList) # no array layout in this file
            arrGroup = dataGroup['Array Layout']
            for key in list(arrGroup.keys()):
                if key.find('Array with') != -1:
                    items = key.split()
                    for item in items:
                        if item.find('=') != -1:
                            subitems = item.split('=')
                            parm = subitems[0].lower()
                            parm = parm.encode('ascii','ignore')
                            retList.append(parm)
                    return(retList)
            
        # None found
        return(retList)
    
    
def listRecords(hdf5Filename, newFilename=None, addedLinkFormat=None):
    """listRecords outputs a summary of records in the hdf5Filename.  Is lower memory footprint than
    loading full file into memory, then calling loadNextRecords.  However, if the file is already fully
    in memory, than classing the MadrigalCedarFile method loadNextRecords is faster.
    
    Inputs:
    
        hdf5Filename - input Madrigal hdf5 file to use
        newFilename - name of new file to create and write to.  If None, the default, write to stdout
        addedLinkFormat - if not None, add link to end of each record with value addedLinkFormat % (recno).
            If None (the default) no added link.  Must contain one and only one integer format to be
            filled in by recno.
    """
    madParmObj = madrigal.data.MadrigalParameters()
    madDataObj = madrigal.data.MadrigalFile(hdf5Filename)
    
    formatStr = '%6i: %s   %s'
    headerStr = ' record    start_time            end_time'
    parms = []
    kinstList = madDataObj.getKinstList()
    if len(kinstList) > 1:
        formatStr += '        %i'
        headerStr += '             kinst'
        parms.append('kinst')
    kindatList = madDataObj.getKindatList()
    if len(kindatList) > 1:
        formatStr += '        %i'
        headerStr += '          kindat'
        parms.append('kindat')
    
    if newFilename is not None:
        f = open(newFilename, 'w')
    else:
        f = sys.stdout
        
    if not addedLinkFormat is None:
        formatStr += '   ' + addedLinkFormat
        headerStr += '    record_plot'
    formatStr += '\n'
        
    f.write('%s\n' % headerStr)
    
    # read in data from file
    with h5py.File(hdf5Filename, 'r') as fi:
        table = fi['Data']['Table Layout']
        recno = table['recno']
        ut1_unix = table['ut1_unix']
        ut2_unix = table['ut2_unix']
        if 'kinst' in parms:
            kinst = table['kinst']
        if 'kindat' in parms:
            kindat = table['kindat']
        
        max_recno = int(recno[-1])
        
        for index in range(max_recno + 1):
            i = numpy.searchsorted(recno, index)
            this_ut1_unix = ut1_unix[i]
            this_ut2_unix = ut2_unix[i]
            if 'kinst' in parms:
                this_kinst = kinst[i]
            if 'kindat' in parms:
                this_kindat = kindat[i]
            
            sDT = datetime.datetime.fromtimestamp(this_ut1_unix, datetime.UTC)
            sDTStr = sDT.strftime('%Y-%m-%d %H:%M:%S')
            eDT = datetime.datetime.fromtimestamp(this_ut2_unix, datetime.UTC)
            eDTStr = eDT.strftime('%Y-%m-%d %H:%M:%S')
            
            data = [index, sDTStr, eDTStr] 
            if 'kinst' in parms:
                data.append(this_kinst)
            if 'kindat' in parms:
                data.append(this_kindat)
            if not addedLinkFormat is None:
                data += [index]
                
            f.write(formatStr % tuple(data))
            
    if f != sys.stdout:
        f.close()

    

class MadrigalCedarFile:
    """MadrigalCedarFile is an object that allows the creation and editing of Cedar files.

    This class emulates a python list, and so users may treat it just like a python list.  The
    restriction enforced is that all items in the list must be either MadrigalCatalogRecords,
    MadrigalHeaderRecords, or MadrigalDataRecords (all also defined in the madrigal.cedar module).
    Each of these three classes supports the method getType(), which returns 'catalog', 'header',
    and 'data', respectively.
    
    There are two programming patterns to choice from when using this module.  For smaller input or output files,
    read in files using the default maxRecords=None, so that the entire file is read into memory.  Output files
    using write for hdf5 or netCDF4 output, or writeText with the default append=False for text files.  This
    will be somewhat faster than using the larger file pattern below.
    
    For larger files, init the reading with maxRecords = some value, and then read in the rest using loadNextRecords.
    Write hdf5 file with a series of dumps, and then close with close(). Write text files using writeText with append
    = True.  Write large netCDF4 files by first creating a large Hdf5 file as above, and then use convertToNetCDF4
    to create the large netCDF4 file. This approach is somewhat slower, but has a limited memory footprint.
 

    Usage example::

        # the following example inserts a catalog record at the beginning of an existing file

        import madrigal.cedar.MadrigalCedarFile, time
    
        cedarObj = madrigal.cedar.MadrigalCedarFile('/opt/madrigal/experiments/1998/mlh/20jan98/mil980120g.003.hdf5')

        startTime = time.mktime((1998,1,20,0,0,0,0,0,0)) - time.timezone

        endTime = time.mktime((1998,1,21,23,59,59,0,0,0)) - time.timezone

        # catLines is a list of 80 character lines to be included in catalog record

        catObj = madrigal.cedar.MadrigalCatalogRecord(31, 1000, 1998,1,20,0,0,0,0,
                                                      1998,1,21,23,59,59,99, catLines)

        cedarObj.insert(0, catObj)

        cedarObj.write()


    Non-standard Python modules used: None


    Change history:
    
    Major rewrite in Jan 2013 as moved to Hdf5 and Madrigal 3.0

    Written by "Bill Rideout":mailto:wrideout@haystack.mit.edu  April. 6, 2005
    """
    
    # cedar special values
    missing  = numpy.nan
    missing_int = numpy.iinfo(numpy.int64).min
    requiredFields = ('year', 'month', 'day', 'hour', 'min', 'sec', 'recno', 'kindat', 'kinst', 
                          'ut1_unix', 'ut2_unix')

    def __init__(self, fullFilename,
		 createFlag=False,
         startDatetime=None,
         endDatetime=None,
         maxRecords=None,
         recDset=None,
         arraySplitParms=None,
         skipArray=False):
        """__init__ initializes MadrigalCedarFile by reading in existing file, if any.

        Inputs:

            fullFilename - either the existing Cedar file in Hdf5 format,
                           or a file to be created. May also be None if this
                           data is simply derived parameters that be written to stdout.

            createFlag - tells whether this is a file to be created.  If False and
                         fullFilename cannot be read, an error is raised.  If True and
                         fullFilename already exists, or fullFilename cannot be created,
                         an error is raised.
                         
            startDatetime - if not None (the default), reject all input records where
                  record end time < startDatetime (datetime.datetime object).
                  Ignored if createFlag == True
    
            endDatetime - if not None (the default), reject all input records where
                  record start time > endDatetime (datetime.datetime object)
                  Ignored if createFlag == True
                  
            maxRecords - the maximum number of records to read into memory
                    Ignored if createFlag == True
                    
            recDset - a numpy recarray with column names the names of all parameters, starting
                with requiredFields.  Values are 1 for 1D (all the required parms are 1D), 2 for
                dependent 2D, and 3 for independent spatial 2D parameters.  If None, self._recDset
                not set until first data record appended.
                
            arraySplitParms - if None (the default), read in arraySplitParms from the exiting file.
                Otherwise set self._arraySplitParms to arraySplitParms, which is a list of 1D or 2D parms
                where each unique set of value of the parms in this list will be used to split the full
                data into separate arrays in Hdf5 or netCDF4 files.  For example arraySplitParms=['beamid']
                would split the data into separate arrays for each beamid. If None and new file is being
                created, no array splitting (self._arraySplitParms = []).
                
            skipArray - if False and any 2D parms, create array layout (the default).  If True, skip array
                layout (typically used when there are too many ind parm value combinations - generally not recommended).
            
	        
        Affects: populates self._privList if file exists.  self._privList is the underlying
            list of MadrigalDataRecords, MadrigalCatalogRecords, and MadrigalHeaderRecords.
            Also populates:
                self._tableDType - the numpy dtype to use to build the table layout  
                self._nextRecord - the index of the next record to read from the input file. Not used if
                    createFlag = True
                    (The following are the input arguments described above)
                self._fullFilename
                self._createFlag
                self._startDatetime
                self._endDatetime
                self._maxRecords
                self._totalDataRecords - number of data records appended (may differ from len(self._privList)
                    if dump called).
                self._minMaxParmDict - a dictionary with key = parm mnems, value = tuple of
                    min, max values (may be nan)
                self._arrDict - a dictionary with key = list of array split parm values found in file,
                    ('' if no spliting), and values = dict of key = 'ut1_unix' and ind 2d parm names (excluding
                    array splitting parms, if also ind 2D parm), and values
                    = python set of all unique values.  Populated only if createFlag=True. Used to create
                    Array Layout
                self._recIndexList - a list of (startIndex, endIndex) for each data record added.  Used to slice out
                    data records from Table Layout
                self._num2DSplit - Number of arraySplitParms that are 2D
                self._closed - a boolean used to determine if the file being created was already closed
                self._useRecno - a state variable used when writing to netCDF4, but repeated times in spite
                    of Madrigal best practices
                
                
            
        
        Returns: void
        """

        if startDatetime:
            startDatetime = startDatetime.replace(tzinfo=datetime.timezone.utc)
        if endDatetime:
            endDatetime = endDatetime.replace(tzinfo=datetime.timezone.utc)
        
        self._privList = []
        self._fullFilename = fullFilename
        self._startDatetime = startDatetime
        self._endDatetime = endDatetime
        self._maxRecords = maxRecords
        self._totalDataRecords = 0
        self._nextRecord = 0
        self._tableDType = None # will be set to the dtype of Table Layout
        self._oneDList = None # will be set when first data record appended
        self._twoDList = None # will be set when first data record appended
        self._ind2DList = None # will be set when first data record appended
        self._arraySplitParms = arraySplitParms
        self._skipArray = bool(skipArray)
        if createFlag:
            self._closed = False
        else:
            self._closed = True # no need to close file only being read
        
        self._hdf5Extensions = ('.hdf5', '.h5', '.hdf')
        
        # keep track of earliest and latest record times
        self._earliestDT = None
        self._latestDT = None
        # summary info
        self._experimentParameters = None
        self._kinstList = [] # a list of all kinsts integers in file
        self._kindatList = [] # a list of all kindats integers in file
        self._status = 'Unknown' # can be externally set
        self._format = None # used to check that partial writes via dump are consistent

        if createFlag not in (True, False):
            raise ValueError('in MadrigalCedarFile, createFlag must be either True or False')
        self._createFlag = createFlag
        self._useRecno = False

        if createFlag == False:
            if not os.access(fullFilename, os.R_OK):
                raise ValueError('in MadrigalCedarFile, fullFilename %s does not exist' % (str(fullFilename)))
            if not fullFilename.endswith(self._hdf5Extensions):
                raise IOError('MadrigalCedarFile can only read in CEDAR Hdf5 files, not %s' % (fullFilename))

        if createFlag == True:
            if fullFilename != None: # then this data will never be persisted - only written to stdout
                if os.access(fullFilename, os.R_OK):
                    raise ValueError('in MadrigalCedarFile, fullFilename %s already exists' % (str(fullFilename)))
                if not os.access(os.path.dirname(fullFilename), os.W_OK):
                    raise ValueError('in MadrigalCedarFile, fullFilename %s cannot be created' % (str(fullFilename)))
                if not fullFilename.endswith(self._hdf5Extensions):
                    raise IOError('All Madrigal files must end with hdf5 extension, <%s> does not' % (str(fullFilename)))
            if self._arraySplitParms is None:
                self._arraySplitParms = []
                
        # create needed Madrigal objects
        self._madDBObj = madrigal.metadata.MadrigalDB()
        self._madInstObj = madrigal.metadata.MadrigalInstrument(self._madDBObj)
        self._madParmObj = madrigal.data.MadrigalParameters(self._madDBObj)
        self._madKindatObj = madrigal.metadata.MadrigalKindat(self._madDBObj)
        
        if not self._arraySplitParms is None:
            self._arraySplitParms = [self._madParmObj.getParmMnemonic(p).lower() for p in self._arraySplitParms]
        
        self._minMaxParmDict = {}
        self._arrDict = {}
        self._num2DSplit = None # will be set to bool when first record added
        self._recIndexList = []
        
        if recDset is not None:
            self._recDset = recDset
        else:
            self._recDset = None

        if createFlag == False:
            self.loadNextRecords(self._maxRecords)
        
                
        
    def loadNextRecords(self, numRecords=None, removeExisting=True):
        """loadNextRecords loads a maximum of numRecords.  Returns tuple of the the number of records loaded, and boolean of whether complete.
        May be less than numRecords if not enough records in the input file.  Returns 0 if no records left.
        
        Inputs:
        
            numRecords - number of records to try to load.  If None, load all remaining records
            
            removeExisting - if True (the default), remove existing records before loading new
                ones.  If False, append new records to existing records.
                
        Returns:
            
                tuple of the the number of records loaded, and boolean of whether complete. 
                May be less than numRecords if not enough records.  
                
        Raises error if file opened with createFlag = True
        """
        if self._createFlag:
            raise IOError('Cannot call loadNextRecords when creating a new MadrigalCedarFile')
        
        if removeExisting:
            self._privList = []
            
        isComplete = False
            
        hdfFile = h5py.File(self._fullFilename, 'r')
        tableDset = hdfFile["Data"]["Table Layout"]
        metadataGroup = hdfFile["Metadata"]
        recDset = metadataGroup["_record_layout"]
        
        if self._nextRecord == 0:
            if self._recDset is None:
                self._recDset = recDset[()]
            elif self._recDset != recDset:
                raise IOError('recDset in first record <%s> does not match expected recDset <%s>' % \
                    (str(recDset), str(self._recDset)))
            self._verifyFormat(tableDset, recDset)
            self._tableDType = tableDset.dtype
            self._experimentParameters = numpy.array(hdfFile["Metadata"]['Experiment Parameters'])
            self._kinstList = self._getKinstList(self._experimentParameters)
            self._kindatList = self._getKindatList(self._experimentParameters)
            if self._arraySplitParms is None:
                self._arraySplitParms = self._getArraySplitParms(hdfFile["Metadata"])
            if 'Experiment Notes' in list(hdfFile["Metadata"].keys()):
                self._appendCatalogRecs(hdfFile["Metadata"]['Experiment Notes'])
                self._appendHeaderRecs(hdfFile["Metadata"]['Experiment Notes'])
            
            
        if self._ind2DList is not None:
            parmObjList = (self._oneDList, self._twoDList, self._ind2DList) # used for performance in load
        else:
            parmObjList = None
            
        # get indices for each record
        recLoaded = 0
        recTested = 0
        if not hasattr(self, 'recnoArr'):
            self.recnoArr = tableDset['recno']
        # read all the records in at once for performance
        if not numRecords is None:
            indices = numpy.searchsorted(self.recnoArr, numpy.array([self._nextRecord, self._nextRecord + numRecords]))
            tableIndices = numpy.arange(indices[0], indices[1])
            if len(tableIndices) > 0:
                fullTableSlice = tableDset[tableIndices[0]:tableIndices[-1]+1]
                fullRecnoArr = fullTableSlice['recno']
        else:
            fullTableSlice = tableDset
            fullRecnoArr = self.recnoArr
            
        while(True):
            if not numRecords is None:
                if len(tableIndices) == 0:
                    isComplete = True
                    break
            if numRecords:
                if recTested >= numRecords:
                    break
                
            # get slices of tableDset and recDset to create next MadrigalDataRecord
            indices = numpy.searchsorted(fullRecnoArr, numpy.array([self._nextRecord, self._nextRecord + 1]))
            tableIndices = numpy.arange(indices[0], indices[1])
            if len(tableIndices) == 0:
                isComplete = True
                break
            tableSlice = fullTableSlice[tableIndices[0]:tableIndices[-1]+1]
            self._recIndexList.append((tableIndices[0],tableIndices[-1]+1))
            self._nextRecord += 1
            
            firstRow = tableSlice[0]
            startDT = datetime.datetime.fromtimestamp(firstRow['ut1_unix'], datetime.UTC)
            stopDT = datetime.datetime.fromtimestamp(firstRow['ut2_unix'], datetime.UTC)
            
            if firstRow['kinst'] not in self._kinstList:
                self._kinstList.append(int(firstRow['kinst']))
                
            if firstRow['kindat'] not in self._kindatList:
                self._kindatList.append(int(firstRow['kindat']))
            
            # find earliest and latest times
            if self._earliestDT is None:
                self._earliestDT = startDT
                self._latestDT = stopDT
            else:
                if startDT < self._earliestDT:
                    self._earliestDT = startDT
                if stopDT > self._latestDT:
                    self._latestDT = stopDT
                    
            recTested += 1 # increment here because the next step may reject it
            
            # check if datetime filter should be applied
            if not self._startDatetime is None or not self._endDatetime is None:
                if not self._startDatetime is None:
                    if stopDT < self._startDatetime:
                        continue
                if not self._endDatetime is None:
                    if startDT > self._endDatetime:
                        isComplete = True
                        break
                    
            if self._ind2DList is None:
                try:
                    indParmList = metadataGroup['Independent Spatial Parameters']['mnemonic']
                    indParms = [item.decode('utf-8') for item in indParmList]
                except:
                    indParms = []
            else:
                indParms = self._ind2DList
                
            newMadDataRec = MadrigalDataRecord(madInstObj=self._madInstObj, madParmObj=self._madParmObj,
                                               dataset=tableSlice, recordSet=self._recDset, 
                                               parmObjList=parmObjList, ind2DList=indParms)
            

            if self._ind2DList is None:
                self._oneDList = newMadDataRec.get1DParms()
                self._twoDList = newMadDataRec.get2DParms()
                self._ind2DList = newMadDataRec.getInd2DParms()
                parmObjList = (self._oneDList, self._twoDList, self._ind2DList) # used for performance in load
                # set self._num2DSplit
                twoDSet = set([o.mnemonic for o in self._twoDList])
                arraySplitSet = set(self._arraySplitParms)
                self._num2DSplit = len(twoDSet.intersection(arraySplitSet))
                
            self._privList.append(newMadDataRec)
            recLoaded += 1
            
        hdfFile.close()
        
        # update minmax
        if self._totalDataRecords > 0:
            self.updateMinMaxParmDict()
        
        return((recLoaded, isComplete))
            
            


    def write(self, format='hdf5', newFilename=None, refreshCatHeadTimes=True,
              arraySplittingParms=None, skipArrayLayout=False, overwrite=False):
        """write persists a MadrigalCedarFile to file.
        
        Note:  There are two ways to write to a MadrigalCedarFile.  Either this method (write) is called after all the
        records have been appended to the MadrigalCedarFile, or dump is called after a certain number of records are appended,
        and then at the end dump is called a final time if there were any records not yet dumped, followed by close.
        The __del__ method will automatically call close if needed, and print a warning that the user should add it to
        their code.
        
        write has the advantage of being simplier, but has the disadvantage for larger files of keeping all those records
        in memory.  dump/close has the advantage of significantly reducing the memory footprint, but is somewhat more complex.

        Inputs:

            format - a format to save the file in.  For now, the allowed values are 
            'hdf5' and 'netCDF4'.  Defaults to 'hdf5'. Use writeText method to get text output.

            newFilename - a filename to save to.  Defaults to self._fullFilename passed into initializer if not given.

            refreshCatHeadTimes - if True (the default), update start and and times in the catalog and header
                records to represent the times in the data.  If False, use existing times in those records.
                
            skipArrayLayout - if True, do not include Array Layout even if there are independent spatial
                parameters.  If False (the default) write Array Layout if there are independent spatial
                parameters and format = 'hdf5'
                
            arraySplittingParms - a list of parameters as mnemonics used to split
                arrays into subarrays.  For example, beamcode would split data with separate beamcodes
                into separate arrays. The number of separate arrays will be up to the product of the number of 
                unique values found for each parameter, with the restriction that combinations with no records will
                not create a separate array. If default None passed in, then set to self._arraySplitParms, 
                set when CEDAR file read in.
                
            overwrite - if False (the default) do not overwrite existing file.  If True, overwrite file is it already exists.
                
        Outputs: None

        Affects: writes a MadrigalCedarFile to file
        """
        if self._format != None:
            raise ValueError('Cannot call write method after calling dump method')
        
        if newFilename is None:
            newFilename = self._fullFilename
            
        if format not in ('hdf5', 'netCDF4'):
            raise ValueError('Illegal format <%s> - must be hdf5 or netCDF4' % (format))
        
        if os.access(newFilename, os.R_OK) and not overwrite:
            raise IOError('newFilename <%s> already exists' % (newFilename))
        
        self._format = format
        
        if arraySplittingParms is None:
            arraySplittingParms = self._arraySplitParms
        if arraySplittingParms is None:
            arraySplittingParms = []
        
        if self._format == 'hdf5':
            if not newFilename.endswith(self._hdf5Extensions):
                raise IOError('filename must end with %s, <%s> does not' % (str(self._hdf5Extensions), newFilename))
            try:
                # we need to make sure this file is closed and then deleted if an error
                f = None # used if next line fails
                f = h5py.File(newFilename, 'w')
                self._writeHdf5Metadata(f, refreshCatHeadTimes)
                self._writeHdf5Data(f)
                if len(self.getIndSpatialParms()) > 0:
                    self._createArrayLayout(f, arraySplittingParms)
                f.close()
            except:
                # on any error, close and delete file, then reraise error
                if f:
                    f.close()
                if os.access(newFilename, os.R_OK):
                    os.remove(newFilename)
                raise
            
        elif self._format == 'netCDF4':
            try:
                # we need to make sure this file is closed and then deleted if an error
                f = None # used if next line fails
                f = netCDF4.Dataset(newFilename, 'w', format='NETCDF4')
                self._writeNetCDF4(f, arraySplittingParms)
                f.close()
            except ValueError:  # try using recno instead of ut1_unix as key
                self._useRecno = True
                try:
                    # we need to make sure this file is closed and then deleted if an error
                    try:
                        f.close()
                    except:
                        pass
                    f = None # used if next line fails
                    f = netCDF4.Dataset(newFilename, 'w', format='NETCDF4')
                    self._writeNetCDF4(f, arraySplittingParms)
                    f.close()
                except:
                    # on any error, close and delete file, then reraise error
                    if f:
                        f.close()
                    if os.access(newFilename, os.R_OK):
                        os.remove(newFilename)
                    raise
            except:
                # on any error, close and delete file, then reraise error
                if f:
                    f.close()
                if os.access(newFilename, os.R_OK):
                    os.remove(newFilename)
                raise
            
        self._closed = True # write ends with closed file
            




    def dump(self, format='hdf5', newFilename=None, parmIndexDict=None):
        """dump appends all the present records in MadrigalCedarFile to file, and removes present data records from MadrigalCedarFile.

        Can be used to append records to a file. Catalog and header records are maintaained.
        
        Typically close is called after all calls to dump. The __del__ method will automatically call 
        close if needed, and print a warning that the user should add it to their code.

        Inputs:

            format - a format to save the file in.  The format argument only exists for backwards
                compatibility - only hdf5 is allowed.  IOError raised is any other argument given.
                
            newFilename - a filename to save to.  Defaults to self._fullFilename passed into initializer if not given.
                
            parmIndexDict - used only for dumping netCDF4

        Outputs: None

        Affects: writes a MadrigalCedarFile to file
        """
        
        if self._format != None:
            if self._format != format:
                raise ValueError('Previous dump format was %s, cannot now use %s' % (str(self._format), str(format)))

        if format not in ('hdf5', 'netCDF4'):
            raise ValueError('Format must be hdf5 for dump, not %s' % (str(format)))
        
        if newFilename is None:
            newFilename = self._fullFilename
        
        if self._format is None:
            # first write - run checks, and create all possible metadata and data
            if os.access(newFilename, os.R_OK):
                raise IOError('newFilename <%s> already exists' % (newFilename))
            if format == 'hdf5':
                if not newFilename.endswith(tuple(list(self._hdf5Extensions) + ['.nc'])):
                    raise IOError('filename must end with %s, <%s> does not' % (str(tuple(list(self._hdf5Extensions) + ['.nc'])), newFilename))
            elif format == 'netCDF4':
                if not newFilename.endswith('.nc'):
                    raise IOError('filename must end with %s, <%s> does not' % ('.nc', newFilename))
            
        if len(self._privList) == 0:
            # nothing to dump
            return
        
        
        if format == 'hdf5':
        
            try:
                # we need to make sure this file is closed and then deleted if an error
                f = None # used if next line fails
                f = h5py.File(newFilename, 'a')
                self._closed = False
                if self.hasArray(f):
                    raise IOError('Cannot call dump for hdf5 after write or close')
                self._writeHdf5Data(f)
                f.close()
            except:
                # on any error, close and delete file, then reraise error
                if f:
                    f.close()
                if os.access(newFilename, os.R_OK):
                    os.remove(newFilename)
                raise
            
        elif format == 'netCDF4':
            if len(self._arraySplitParms) != 0:
                raise IOError('Cannot dump netCDF4 files with arraySplitParms - write to Hdf5 and then convert')
            if self._format is None:
                # first write
                try:
                    f = netCDF4.Dataset(newFilename, 'w', format='NETCDF4')
                    self._firstDumpNetCDF4(f, parmIndexDict)
                    f.close()
                except:
                    # try replacing ut1_unix with recno
                    self._useRecno = True
                    try:
                        f,close()
                    except:
                        pass
                    f = netCDF4.Dataset(newFilename, 'w', format='NETCDF4')
                    self._firstDumpNetCDF4(f, parmIndexDict)
                    f.close()
            else:
                f = netCDF4.Dataset(newFilename, 'a', format='NETCDF4')
                self._appendNetCDF4(f, parmIndexDict)
                f.close()
            
                

        self._format = format
        
        # dump data records out of memory
        self._privList = [rec for rec in self._privList if not rec.getType() == 'data']
        
        
    def close(self):
        """close closes an open MadrigalCedarFile.  It calls _writeHdf5Metadata and _addArray if ind parms.
        
        Most be called directly when dump used.
        """
        if self._closed:
            # nothing to do
            return
        
        with h5py.File(self._fullFilename, 'a') as f:
            self._writeHdf5Metadata(f, refreshCatHeadTimes=True)
            
        if len(self.getIndSpatialParms()) > 0:
            if not self._skipArray:
                self._addArrayDump()
            
        self._closed = True
        
        
        
    def writeText(self, newFilename=None, summary='plain', showHeaders=False, selectParms=None,
                  filterList=None, missing=None, assumed=None, knownbad=None, append=False,
                  firstWrite=False):
        """writeText writes text to new filename
        
        Inputs:
        
            newFilename - name of new file to create and write to.  If None, the default, write to stdout
            
            summary - type of summary line to print at top.  Allowed values are:
                'plain' - text only mnemonic names, but only if not showHeaders
                'html' - mnemonic names wrapped in standard javascript code to allow descriptive popups
                'summary' - print overview of file and filters used. Also text only mnemonic names, 
                    but only if not showHeaders
                None - no summary line
                
            showHeaders - if True, print header in format for each record.  If False, the default,
                do not.
                
            selectParms - If None, simply print all parms that are in the file.  If a list
                of parm mnemonics, print only those parms in the order specified.
                
            filterList - a list of madrigal.derivation.MadrigalFilter objects to be described in the 
                summary.  Default is None, in which case not described in summary.  Ignored if summary
                is not 'summary'
                
            missing, assumed, knownbad - how to print Cedar special values.  Default is None for
                all, so that value printed in value in numpy table as per spec.
                
            append - if True, open newFilename in append mode, and dump records after writing.  If False, 
                open in write mode. Used to allow writing in conjuction with loadNextRecords.
                
            firstWrite - True if this is the first group of records added, and append mode is True.
                Used to know whether to write summary lines.  If False and append is True, no summary
                lines are added; if True and append is True, summary lines are added.  If append is not 
                True, this argument ignored.
                
        """
        # constants 
        _underscore = 95 # used to indicate missing character
        _reStr = "b\'[^\']+\'" # used to modify binary strings
        
        if newFilename is not None:
            if append:
                f = open(newFilename, 'a')
            else:
                f = open(newFilename, 'w')
        else:
            f = sys.stdout
            
        if summary not in ('plain', 'summary', 'html', None):
            raise ValueError('Illegal summary value <%s>' % (str(summary)))
        
        # cache information needed to replace special values if needed
        # helps performance when replacing
        if missing is not None:
            missing = str(missing)
            missing_len = len(missing)
            missing_search = r'\ ' * max(0, missing_len-3) + 'nan'
            if missing_len < 3:
                missing = ' ' * (3-missing_len) + missing
        if assumed is not None:
            assumed = str(assumed)
            assumed_len = len(assumed)
            assumed_search = r'\ ' * max(0, assumed_len-3) + 'inf'
            if assumed_len < 3:
                assumed = ' ' * (3-assumed_len) + assumed
        if knownbad is not None:
            knownbad = str(knownbad)
            knownbad_len = len(knownbad)
            knownbad_search = r'\ ' * max(0, knownbad_len-4) + '-inf'
            if knownbad_len < 4:
                knownbad = ' ' * (4-knownbad_len) + knownbad
            
        # create format string and header strings
        formatStr = ''
        parmStr = ''
        hasString = False # if string parm found, remove b' ' around the output
        if not selectParms is None:
            names = selectParms
        else:
            names = self._tableDType.names
        for parm in names:
            parm = parm.upper()
            format = self._madParmObj.getParmFormat(parm)
            try:
                # first handle float formats
                dataWidth = int(format[1:format.find('.')])
                # make sure width is big enough for special values
                newDataWidth = dataWidth
                if missing is not None:
                    newDataWidth = max(newDataWidth, len(missing)+1)
                if self._madParmObj.isError(parm):
                    if assumed is not None:
                        newDataWidth = max(newDataWidth, dataWidth, len(assumed)+1)
                    if knownbad is not None:
                        newDataWidth = max(newDataWidth, dataWidth, len(knownbad)+1)
                if newDataWidth > dataWidth:
                    # we need to expand format
                    format = '%%%i%s' % (newDataWidth, format[format.find('.'):])
                    dataWidth = newDataWidth
                if format.find('S') != -1 or format.find('s') != -1:
                    hasString = True
            except ValueError:
                # now handle integer or string formats - assumed to never be error values
                if format.find('i') != -1:
                    if len(format) == 2:
                        # we need to insert a length
                        format = '%%%ii' % (self._madParmObj.getParmWidth(parm)-1)
                        dataWidth = self._madParmObj.getParmWidth(parm)
                    else:
                        dataWidth = int(format[1:-1])
                elif format.find('S') != -1 or format.find('s') != -1:
                    hasString = True
                    dataWidth = int(format[1:-1])
                else:
                    raise
            width = max(self._madParmObj.getParmWidth(parm), dataWidth)
            formatStr += '%s' % (format)
            formatStr += ' ' * (max(1, width-dataWidth)) # sets spacing between numbers
            if len(parm) >= width-1:
                # need to truncate name
                if summary != 'html':
                    parmStr += parm[:width-1] + ' '
                else:
                    parmStr += "<a href=JavaScript:popup('%s') title='%s, units=%s'>%s</a>&nbsp;" % (parm[:width-1].upper(),
                                                                                                     self._madParmObj.getSimpleParmDescription(parm),
                                                                                                     self._madParmObj.getParmUnits(parm),
                                                                                                     parm[:width-1].upper())
            else:
                # pad evenly on both sides
                firstHalfSpace = int((width-len(parm))/2)
                secHalfSpace = int((width-len(parm)) - firstHalfSpace)
                if summary != 'html':
                    parmStr += ' ' * firstHalfSpace + parm.upper() + ' ' * secHalfSpace
                else:
                    parmStr += '&nbsp;' * firstHalfSpace 
                    parmStr += "<a href=JavaScript:popup('%s') title='%s, units=%s'>%s</a>" % (parm[:width-1].upper(),
                                                                                               self._madParmObj.getSimpleParmDescription(parm),
                                                                                               self._madParmObj.getParmUnits(parm),
                                                                                               parm[:width-1].upper())
                    parmStr += '&nbsp;' * secHalfSpace
                    
        formatStr += '\n'
        firstHeaderPrinted = False # state variable for adding extra space between lines
        
        if summary == 'summary': 
            if not append or (append and firstWrite):
                self._printSummary(f, filterList)
        
        if summary in ('plain', 'summary', 'html') and not showHeaders:
            if not append or (append and firstWrite):
                # print single header at top
                f.write('%s\n' % (parmStr))
                if summary == 'html':
                    f.write('<br>\n')
            
        if len(self._privList) == 0:
            # nothing more to write
            if f != sys.stdout:
                f.close()
            return
        
        # see if only 1D parms are selected, which implies printing only a single line per record
        is1D = False
        if not selectParms is None:
            #make sure its a lowercase list
            selectParms = list(selectParms)
            selectParms = getLowerCaseList(selectParms)
            # see if only 1D parameters are being printed, so that we should only print the first row
            is1D = True
            recordset = self.getRecordset()
            for parm in selectParms:
                if recordset[parm][0] != 1:
                    is1D = False
                    break
                
        for rec in self._privList:
            if rec.getType() != 'data':
                continue
            
            if showHeaders:
                kinst = rec.getKinst()
                instDesc = self._madInstObj.getInstrumentName(kinst)
                sDT = rec.getStartDatetime()
                sDTStr = sDT.strftime('%Y-%m-%d %H%M:%S')
                eDT = rec.getEndDatetime()
                eDTStr = eDT.strftime('%H%M:%S')
                headerStr = '%s: %s-%s\n' % (instDesc, sDTStr, eDTStr)
                if firstHeaderPrinted or summary is None:
                    f.write('\n%s' % (headerStr))
                else:
                    f.write('%s' % (headerStr))
                    firstHeaderPrinted = True
                f.write('%s\n' % (parmStr))
                
            dataset = rec.getDataset()
            if not selectParms is None:
                recnoSet = dataset['recno'].copy() # used to see if we are at a new record
                dataset_view = dataset[selectParms].copy()
            else:
                dataset_view = dataset
                
            # modify special values if required
            if assumed is not None or knownbad is not None:
                for name in dataset_view.dtype.names:
                    if self._madParmObj.isError(name) and not self.parmIsInt(name):
                        if assumed is not None:
                            # set all -1 values to inf
                            assumedIndices = numpy.where(dataset_view[name] == -1.0)
                            if len(assumedIndices):
                                dataset_view[name][assumedIndices] = numpy.inf
                        if knownbad is not None:
                            # set all -2 values to ninf
                            knownbadIndices = numpy.where(dataset_view[name] == -2.0)
                            if len(knownbadIndices):
                                dataset_view[name][knownbadIndices] = -numpy.inf
                            
            lastRecno = None
            for i in range(len(dataset_view)):
                if not selectParms is None:
                    thisRecno = recnoSet[i]
                    if is1D and (thisRecno == lastRecno):
                        continue
                data = tuple(list(dataset_view[i]))
                try:
                    text = formatStr % data
                except:
                    # something bad happened - give up and just convert data to a string
                    textList = [str(item) for item in data]
                    delimiter = ' '
                    text = delimiter.join(textList) + '\n'
                # modify special values if required
                if missing is not None:
                    if text.find('nan') != -1:
                        text = re.sub(missing_search, missing, text)
                if knownbad is not None:
                    if text.find('-inf') != -1:
                        text = re.sub(knownbad_search, knownbad, text)
                if assumed is not None:
                    if text.find('inf') != -1:
                        text = re.sub(assumed_search, assumed, text)
                if hasString:
                    text = re.sub(_reStr, fixBinaryString, text)
                
                if summary != 'html':
                    f.write(text)
                else:
                    f.write(text.replace(' ', '&nbsp;'))
                if summary == 'html':
                    f.write('<br>\n')
                if not selectParms is None:
                    lastRecno = thisRecno
                    
        if f != sys.stdout:
            f.close()
            
        if append:
            # remove all records
            self._privList = []
            
        
        
    def getDType(self):
        """getDType returns the dtype of the table array in this file
        """
        return(self._tableDType)
    
    
    def setDType(self, dtype):
        """setDType sets the dtype of the table array
        """
        self._tableDType = dtype
        
        
    def getRecDType(self):
        """getRecDType returns the dtype of _record_layout
        """
        return(self._recDset.dtype)
        
        
    def getRecordset(self):
        """getRecordset returns the recordset array from the first data record.
        
        Raises IOError if None
        """
        if self._recDset is None:
            raise IOError('self._recDset is None')
        return(self._recDset)
    
    
    def get1DParms(self):
        """get1DParms returns a list of mnemonics of 1D parms
        in file.  May be empty if none. 
        
        Raises ValueError if self._oneDList is None, since parameters unknown
        """
        if self._oneDList is None:
            raise ValueError('get1DParms cannot be called before any data records added to this file')
        
        retList = []
        for parm in self._oneDList:
            retList.append(parm.mnemonic)
        return(retList)
    
    
    def get2DParms(self):
        """get2DParms returns a list of mnemonics of dependent 2D parms
        in file.  May be empty if none. 
        
        Raises ValueError if self._twoDList is None, since parameters unknown
        """
        if self._twoDList is None:
            raise ValueError('get2DParms cannot be called before any data records added to this file')
        
        retList = []
        for parm in self._twoDList:
            retList.append(parm.mnemonic)
        return(retList)
        
        
        
    def getIndSpatialParms(self):
        """getIndSpatialParms returns a list of mnemonics of independent spatial parameters
        in file.  May be empty if none. 
        
        Raises ValueError if self._ind2DList is None, since parameters unknown
        """
        if self._ind2DList is None:
            raise ValueError('getIndSpatialParms cannot be called before any data records added to this file')
        
        retList = []
        for parm in self._ind2DList:
            retList.append(parm.mnemonic)
        return(retList)
    
    def getArraySplitParms(self):
        """getArraySplitParms returns a list of mnemonics of parameters used to split array.  May be empty or None. 
        """
        return(self._arraySplitParms)
    
    
    def getParmDim(self, parm):
        """getParmDim returns the dimension (1,2, or 3 for independent spatial parms) of input parm
        
        Raises ValueError if no data records yet.
        Raise KeyError if that parameter not found in file
        """
        if self._ind2DList is None:
            raise ValueError('getParmDim cannot be called before any data records added to this file')
        
        for obj in self._oneDList:
            if obj.mnemonic.lower() == parm.lower():
                return(1)
        # do ind 2D next since they are in both lists
        for obj in self._ind2DList:
            if obj.mnemonic.lower() == parm.lower():
                return(3)
        for obj in self._twoDList:
            if obj.mnemonic.lower() == parm.lower():
                return(2)
        
        raise KeyError('Parm <%s> not found in data' % (str(parm)))
        
        
    def getStatus(self):
        """getStatus returns the status string
        """
        return(self._status)
    
    
    def setStatus(self, status):
        """setStatus sets the status string
        """
        self._status = str(status)
        
        
    def getEarliestDT(self):
        """getEarliestDT returns the earliest datetime found in file, or None if no data
        """
        return(self._earliestDT)
    
    
    def getLatestDT(self):
        """getLatestDT returns the latest datetime found in file, or None if no data
        """
        return(self._latestDT)
    
    
    def getKinstList(self):
        """getKinstList returns the list of kinst integers in the file
        """
        return(self._kinstList)
    
    
    def getKindatList(self):
        """getKindatList returns the list of kindat integers in the file
        """
        return(self._kindatList)
    
    def getRecIndexList(self):
        """getRecIndexList returns a list of record indexes into Table Layout
        """
        return(self._recIndexList)
    
    
    def parmIsInt(self, parm):
        """parmIsInt returns True if this parm (mnemonic) is integer type, False if not
        
        Raises ValueError if parm not in record. or table dtype not yet set
        """
        if self._tableDType is None:
            raise ValueError('Cannot call parmIsInt until a data record is added')
        try:
            typeStr = str(self._tableDType[parm.lower()])
        except KeyError:
            raise ValueError('Parm <%s> not found in file' % (str(parm)))
        if typeStr.find('int') != -1:
            return(True)
        else:
            return(False)
        
    def parmIsString(self, parm):
        """parmIsString returns True if this parm (mnemonic) is string type, False if not
        
        Raises ValueError if parm not in record. or table dtype not yet set
        """
        if self._tableDType is None:
            raise ValueError('Cannot call parmIsInt until a data record is added')
        try:
            typeStr = str(self._tableDType[parm.lower()])
        except KeyError:
            raise ValueError('Parm <%s> not found in file' % (str(parm)))
        if typeStr.lower().find('s') == -1:
            return(False)
        else:
            return(True)
        
        
    def getStringFormat(self, parm):
        """getStringFormat returns string format string.  Raises error if not string type,
        or parm not in record. or table dtype not yet set
        """
        if not self.parmIsString(parm):
            raise ValueError('parm %s not a string, cannot call getStringFormat' % (str(parm)))
        return(str(self._tableDType[parm.lower()]))
        
        
    def hasArray(self, f):
        """hasArray returns True in f['Data']['Array Layout'] exists, False otherwise
        """
        if 'Data' in list(f.keys()):
            if 'Array Layout' in list(f['Data'].keys()):
                return(True)
            
        return(False)
    
    
    def getMaxMinValues(self, mnemonic, verifyValid=False):
        """getMaxMinValues returns a tuple of (minimum value, maximum value) of the value
        of parm in this file.  If verifyValid is True, then only lines with valid 2D data
        are included.  If no valid values, returns (NaN, NaN). Also updates self._minMaxParmDict
        
        Raise IOError if parm not found
        """
        parm = mnemonic.lower()
        
        # for string data, always return (Nan, Nan)
        if self._madParmObj.isString(parm):
            self._minMaxParmDict[parm] = [numpy.nan, numpy.nan]
            return((numpy.nan, numpy.nan))
        
        # create a merged dataset
        datasetList = []
        for rec in self._privList:
            
            if rec.getType() == 'data':
                datasetList.append(rec._dataset)
                
        if len(datasetList) == 0:
            if parm in self._minMaxParmDict:
                return(self._minMaxParmDict[parm])
            else:
                raise IOError('No data records in file')
        
        merged_dataset = numpy.concatenate(datasetList)
        
        if not verifyValid:
            # veru simple - just jusr numpy methods
            try:
                data = merged_dataset[parm]
            except:
                raise IOError('parm %s not found in file' % (parm))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                minValue = numpy.nanmin(data)
                maxValue = numpy.nanmax(data)
            if parm not in self._minMaxParmDict:
                self._minMaxParmDict[parm] = [minValue, maxValue]
            else:
                orgMin, orgMax = self._minMaxParmDict[parm]
                self._minMaxParmDict[parm] = [min(minValue, orgMin), max(maxValue, orgMax)]
            return((minValue, maxValue))
        
        # we need to find the minimum and maximum for only valid data
        # first sort by parm so we just need to walk until we find a valid row starting at the top and bottom
        sorted_indices = numpy.argsort(merged_dataset[parm])
        
        # find min
        minValue = None
        for i in sorted_indices:
            if numpy.isnan(merged_dataset[parm][i]):
                continue
            for twoDParm in self.get2DParms():
                if self._madParmObj.isString(twoDParm):
                    continue
                if numpy.isnan(merged_dataset[twoDParm][i]):
                    continue
                # make sure its not a special error value
                if self._madParmObj.isError(twoDParm) and merged_dataset[twoDParm][i] < 0:
                    continue
                # minimum found
                minValue = merged_dataset[parm][i]
                break
            if not minValue is None:
                break
            
        # find max
        maxValue = None
        for i in reversed(sorted_indices):
            if numpy.isnan(merged_dataset[parm][i]):
                continue
            for twoDParm in self.get2DParms():
                if self._madParmObj.isString(twoDParm):
                    continue
                if numpy.isnan(merged_dataset[twoDParm][i]):
                    continue
                # make sure its not a special error value
                if self._madParmObj.isError(twoDParm) and merged_dataset[twoDParm][i] < 0:
                    continue
                # minimum found
                maxValue = merged_dataset[parm][i]
                break
            if not maxValue is None:
                break
                
        if minValue is None:
            minValue = numpy.nan
        if maxValue is None:
            maxValue = numpy.nan
            
        if parm not in self._minMaxParmDict:
            self._minMaxParmDict[parm] = [minValue, maxValue]
        else:
            orgMin, orgMax = self._minMaxParmDict[parm]
            self._minMaxParmDict[parm] = [min(minValue, orgMin), max(maxValue, orgMax)]
            
        return((minValue, maxValue))
    
    
    def refreshSummary(self):
        """refreshSummary rebuilds the recarray self._experimentParameters
        """
        inst = int(self.getKinstList()[0])
        delimiter = ','
        kinstCodes = []
        kinstNames = []
        for code in self.getKinstList():
            kinstCodes.append(str(int(code)))
            kinstNames.append(str(self._madInstObj.getInstrumentName(int(code))))
        instrumentCodes = delimiter.join(kinstCodes)
        instrumentName = delimiter.join(kinstNames)
        
        categoryStr = self._madInstObj.getCategory(inst)
        piStr = self._madInstObj.getContactName(inst)
        piEmailStr = self._madInstObj.getContactEmail(inst)
        
        startDateStr = self.getEarliestDT().strftime('%Y-%m-%d %H:%M:%S UT')
        endDateStr = self.getLatestDT().strftime('%Y-%m-%d %H:%M:%S UT')
        
        cedarFileName = str(os.path.basename(self._fullFilename))

        statusDesc = self._status
        instLat = self._madInstObj.getLatitude(inst)
        instLon = self._madInstObj.getLongitude(inst)
        instAlt = self._madInstObj.getAltitude(inst)
        
        # create kindat description based on all kindats
        kindatList = self.getKindatList()
        kindatDesc = ''
        kindatListStr = ''
        if len(kindatList) > 1:
            kindatDesc = 'This experiment has %i kinds of data.  They are:' % (len(kindatList))
            for i, kindat in enumerate(kindatList):
                thisKindatDesc = self._madKindatObj.getKindatDescription(kindat, inst)
                if not thisKindatDesc:
                    raise IOError('kindat %i undefined - please add to typeTab.txt' % (kindat))
                thisKindatDesc = thisKindatDesc.strip()
                kindatDesc += ' %i) %s (code %i)' % (i+1, thisKindatDesc, kindat)
                kindatListStr += '%i' % (kindat)
                if i < len(kindatList) - 1:
                    kindatDesc += ', '
                    kindatListStr += ', '
        else:
            kindatDesc = self._madKindatObj.getKindatDescription(kindatList[0], inst)
            if not kindatDesc:
                raise IOError('kindat for %s undefined - please add to typeTab.txt' % (str((kindatList[0], inst))))
            kindatDesc = kindatDesc.strip()
            kindatListStr += '%i' % (kindatList[0])
            
        # create an expSummary numpy recarray  
        summArr = numpy.recarray((14,), dtype = [('name', h5py.special_dtype(vlen=str) ),
                                                ('value', h5py.special_dtype(vlen=str) )])
        
        summArr['name'][0] = 'instrument'
        summArr['name'][1] = 'instrument code(s)'
        summArr['name'][2] = 'kind of data file'
        summArr['name'][3] = 'kindat code(s)'
        summArr['name'][4] = 'start time'
        summArr['name'][5] = 'end time'
        summArr['name'][6] = 'Cedar file name'
        summArr['name'][7] = 'status description'
        summArr['name'][8] = 'instrument latitude'
        summArr['name'][9] = 'instrument longitude'
        summArr['name'][10] = 'instrument altitude'
        summArr['name'][11] = 'instrument category'
        summArr['name'][12] = 'instrument PI'
        summArr['name'][13] = 'instrument PI email'
                      
        summArr['value'][0] = instrumentName
        summArr['value'][1] = instrumentCodes
        summArr['value'][2] = kindatDesc
        summArr['value'][3] = kindatListStr
        summArr['value'][4] = startDateStr
        summArr['value'][5] = endDateStr
        summArr['value'][6] = cedarFileName
        summArr['value'][7] = statusDesc
        summArr['value'][8] = str(instLat)
        summArr['value'][9] = str(instLon)
        summArr['value'][10] = str(instAlt)
        summArr['value'][11] = categoryStr
        summArr['value'][12] = piStr
        summArr['value'][13] = piEmailStr
        
        self._experimentParameters = summArr

        
        
    def createCatalogTimeSection(self):
        """createCatalogTimeSection will return all the lines in the catalog record that
        describe the start and end time of the data records.

        Inputs: None

        Returns:  a tuple with three items 1) a string in the format of the time section of a
        catalog record, 2) earliest datetime, 3) latest datetime
        """

        earliestStartTime = self.getEarliestDT()
        latestEndTime = self.getLatestDT()

        sy = 'IBYRE       %4s Beginning year' % (str(earliestStartTime.year))
        sd = 'IBDTE       %4s Beginning month and day' % (str(earliestStartTime.month*100 + \
                                                              earliestStartTime.day))
        sh = 'IBHME       %4s Beginning UT hour and minute' % (str(earliestStartTime.hour*100 + \
                                                                   earliestStartTime.minute))
        totalCS = earliestStartTime.second*100 + (earliestStartTime.microsecond/10000)
        ss = 'IBCSE       %4s Beginning centisecond'  % (str(totalCS))
        
        ey = 'IEYRE       %4s Ending year' % (str(latestEndTime.year))
        ed = 'IEDTE       %4s Ending month and day' % (str(latestEndTime.month*100 + \
                                                           latestEndTime.day))
        eh = 'IEHME       %4s Ending UT hour and minute' % (str(latestEndTime.hour*100 + \
                                                                latestEndTime.minute))
        totalCS = latestEndTime.second*100 + (latestEndTime.microsecond/10000)
        es = 'IECSE       %4s Ending centisecond'  % (str(totalCS))

        retStr = ''
        retStr += sy + (80-len(sy))*' '
        retStr += sd + (80-len(sd))*' '
        retStr += sh + (80-len(sh))*' '
        retStr += ss + (80-len(ss))*' '
        retStr += ey + (80-len(ey))*' '
        retStr += ed + (80-len(ed))*' '
        retStr += eh + (80-len(eh))*' '
        retStr += es + (80-len(es))*' '

        return((retStr, earliestStartTime, latestEndTime))
    
    
    def createHeaderTimeSection(self, dataRecList=None):
        """createHeaderTimeSection will return all the lines in the header record that
        describe the start and end time of the data records.

        Inputs:

            dataRecList - if given, examine only those MadrigalDataRecords in dataRecList.
                          If None (the default), examine all MadrigalDataRecords in this
                          MadrigalCedarFile

        Returns:  a tuple with three items 1) a string in the format of the time section of a
        header record, 2) earliest datetime, 3) latest datetime
        """
        if dataRecList is None:
            earliestStartTime = self.getEarliestDT()
            latestEndTime = self.getLatestDT()

        else:
            earliestStartTime = None
            latestEndTime = None
    
            for rec in dataRecList:
                if rec.getType() != 'data':
                    continue
    
                #earliest time
                thisTime = rec.getStartDatetime()
                if earliestStartTime is None:
                    earliestStartTime = thisTime
                if earliestStartTime > thisTime:
                    earliestStartTime = thisTime
    
                #latest time
                thisTime = rec.getEndDatetime()
                if latestEndTime is None:
                    latestEndTime = thisTime
                if latestEndTime < thisTime:
                    latestEndTime = thisTime
                

        sy = 'IBYRT               %4s Beginning year' % (str(earliestStartTime.year))
        sd = 'IBDTT               %4s Beginning month and day' % (str(earliestStartTime.month*100 + \
                                                              earliestStartTime.day))
        sh = 'IBHMT               %4s Beginning UT hour and minute' % (str(earliestStartTime.hour*100 + \
                                                                   earliestStartTime.minute))
        totalCS = earliestStartTime.second*100 + (earliestStartTime.microsecond/10000)
        ss = 'IBCST               %4s Beginning centisecond'  % (str(totalCS))
        
        ey = 'IEYRT               %4s Ending year' % (str(latestEndTime.year))
        ed = 'IEDTT               %4s Ending month and day' % (str(latestEndTime.month*100 + \
                                                           latestEndTime.day))
        eh = 'IEHMT               %4s Ending UT hour and minute' % (str(latestEndTime.hour*100 + \
                                                                latestEndTime.minute))
        totalCS = latestEndTime.second*100 + (latestEndTime.microsecond/10000)
        es = 'IECST               %4s Ending centisecond'  % (str(totalCS))

        retStr = ''
        retStr += sy + (80-len(sy))*' '
        retStr += sd + (80-len(sd))*' '
        retStr += sh + (80-len(sh))*' '
        retStr += ss + (80-len(ss))*' '
        retStr += ey + (80-len(ey))*' '
        retStr += ed + (80-len(ed))*' '
        retStr += eh + (80-len(eh))*' '
        retStr += es + (80-len(es))*' '

        return((retStr, earliestStartTime, latestEndTime))
    
    
    def updateMinMaxParmDict(self):
        """updateMinMaxParmDict updates self._minMaxParmDict
        """
        for parm in self.get1DParms() + self.get2DParms():
            self.getMaxMinValues(parm, True)
    
    
    def _writeHdf5Metadata(self, f, refreshCatHeadTimes):
        """_writeHdf5Metadata is responsible for writing Metadata group in Hdf5 file
        
        Can be called multiple times, but will only write "Experiment Notes" if any catalog or header
        records found
        
        Inputs: 
        
            f - the open h5py.File object
            
            refreshCatHeadTimes - if True, update start and and times in the catalog and header
                records to represent the times in the data.  If False, use existing times in those records.
        """
        if "Metadata" not in list(f.keys()):
            # metadata tables that are only updated once
            metadataGroup = f.create_group("Metadata")
            self._addDataParametersTable(metadataGroup)
            if self._experimentParameters is None:
                self.refreshSummary()
            metadataGroup.create_dataset('Experiment Parameters', data=self._experimentParameters)
            
            # create Independent Spatial Parameters recordset
            indParmList = self.getIndSpatialParms()
            indParmDesc = []
            longestMnemStr = 1
            longestDescStr = 1
            for indParm in indParmList:
                if len(indParm) > longestMnemStr:
                    longestMnemStr = len(indParm)
                indParmDesc.append(self._madParmObj.getSimpleParmDescription(indParm))
                if len(indParmDesc[-1]) > longestDescStr:
                    longestDescStr = len(indParmDesc[-1])
            indSpatialArr = numpy.recarray((len(indParmList),),
                                         dtype = [('mnemonic', '|S%i' % (longestMnemStr)),
                                                  ('description', '|S%i' % (longestDescStr))])
            for i, indParm in enumerate(indParmList):
                indSpatialArr[i]['mnemonic'] = indParm
                indSpatialArr[i]['description'] = indParmDesc[i]
            
            metadataGroup.create_dataset('Independent Spatial Parameters', data=indSpatialArr)
            
        else:
            metadataGroup = f["Metadata"]
        self._writeRecordLayout(metadataGroup)
        self.writeExperimentNotes(metadataGroup, refreshCatHeadTimes)
        
        
        
    def _addArrayDump(self):
        """_addArrayDump adds Array Layout to an Hdf5 file created by dump.  

        Inputs: None 
                
        Outputs: None

        Affects: adds "Array Layout" group to f['Data']
        """
        if self._format != 'hdf5':
            raise ValueError('Can only call _addArrayDump for Hdf5 files written using dump')
        
        self._createArrayLayout2()
        
        # try to gzip 2d array data
        filename, file_extension = os.path.splitext(self._fullFilename)
        # tmp file name to use to run h5repack
        tmpFile = filename + '_tmp' + file_extension
        cmd = 'h5repack -i %s -o %s --filter=\"Data/Array Layout\":GZIP=4' % (self._fullFilename, tmpFile)
        try:
            subprocess.check_call(shlex.split(cmd))
        except:
            traceback.print_exc()
            return
        
        shutil.move(tmpFile, self._fullFilename)
        
    
    
    
    def _writeHdf5Data(self, f):
        """_writeHdf5Data is responsible for writing Data group in Hdf5 file
        
        Input: f - the open h5py.File object
        """
        
        tableName = 'Table Layout'
        
        # create a merged dataset
        datasetList = []
        nrows = None
        for rec in self._privList:
            
            if rec.getType() == 'data':
                datasetList.append(rec._dataset)
                if nrows is None:
                    nrows = rec.getNrow()
                
        if len(datasetList) == 0:
            raise IOError('No data records in file')
        
        merged_dataset = numpy.concatenate(datasetList)
        
        if "Data" not in list(f.keys()):
            dataGroup = f.create_group("Data")
            dset = dataGroup.create_dataset(tableName, data=merged_dataset, compression='gzip', maxshape=(None,),
                                            chunks=True)
        else:
            # append
            dataGroup = f["Data"]
            added_len = merged_dataset.shape[0]
            dset = dataGroup[tableName]
            dset.resize((dset.shape[0] + added_len,))
            dset.write_direct(merged_dataset,None,numpy.s_[-1*added_len:])
        
        del(merged_dataset)
        
        
    def _createArrayLayout(self, f, arraySplittingParms):
        """_createArrayLayout will append an Array Layout to the open Hdf5 file f
        
        arraySplittingParms - a list of parameters as mnemonics used to split
            arrays into subarrays.  For example, beamcode would split data with separate beamcodes
            into separate arrays. The number of separate arrays will be up to the product of the number of 
            unique values found for each parameter, with the restriction that combinations with no records will
            not create a separate array.
        
        IOError raised if Array Layout already exists - this can only be called once
        """
        if self._skipArray:
            return
        
        # get info from recarrays that already exist
        table = f['Data']['Table Layout']
        recLayout = f['Metadata']['_record_layout']
        metadataGroup = f['Metadata']
        
        # inputs
        indParmList = self.getIndSpatialParms()
        
        if "Array Layout" in list(f['Data'].keys()):
            raise IOError('Array Layout already created - this can only be created once.')
        
        # add "Parameters Used to Split Array Data" to Metadata
        if len(arraySplittingParms) > 0:
            arrSplitParmDesc = []
            longestMnemStr = 0
            longestDescStr = 0
            for arrSplitParm in arraySplittingParms:
                if len(arrSplitParm) > longestMnemStr:
                    longestMnemStr = len(arrSplitParm)
                arrSplitParmDesc.append(self._madParmObj.getSimpleParmDescription(arrSplitParm))
                if len(arrSplitParmDesc[-1]) > longestDescStr:
                    longestDescStr = len(arrSplitParmDesc[-1])
            arrSplitArr = numpy.recarray((len(arraySplittingParms),),
                                         dtype = [('mnemonic', '|S%i' % (longestMnemStr)),
                                                  ('description', '|S%i' % (longestDescStr))])
            for i, arrSplitParm in enumerate(arraySplittingParms):
                arrSplitArr[i]['mnemonic'] = arrSplitParm
                arrSplitArr[i]['description'] = arrSplitParmDesc[i]
            
            metadataGroup.create_dataset('Parameters Used to Split Array Data', data=arrSplitArr)
            

        arrGroup = f['Data'].create_group("Array Layout")
        
        arraySplittingList = [] # list of lists of all existing values for each array splitting parm
        for parm in arraySplittingParms:
            arraySplittingList.append(numpy.unique(table[parm]))
        
        tableSubsets = []
        for combo in itertools.product(*arraySplittingList):
            tableSubsets.append(_TableSubset(arraySplittingParms, combo, table))
        
        for tableSubset in tableSubsets:
            uniqueIndValueDict = {}
            for indParm in indParmList:
                uniqueIndValueDict[indParm] = numpy.unique(tableSubset.table[indParm])
            unique_times = numpy.unique(tableSubset.table['ut1_unix'])
            group_name = tableSubset.getGroupName()
            if group_name != None:
                thisGroup = arrGroup.create_group(tableSubset.getGroupName())
            else:
                thisGroup = arrGroup # no splitting, so no subgroup needed
            self._addLayoutDescription(thisGroup)
            ts_dset = thisGroup.create_dataset("timestamps", data=unique_times)
            for indParm in indParmList:
                thisGroup.create_dataset(indParm, data=uniqueIndValueDict[indParm])
                
            # one D parm arrays
            oneDGroup = thisGroup.create_group('1D Parameters')
            self._addDataParametersTable(oneDGroup, 1)
            for parm in recLayout.dtype.names[len(self.requiredFields):]:
                if recLayout[parm][0] == 1:
                    dset = tableSubset.table[parm][tableSubset.oneDIndices]
                    oneDGroup.create_dataset(parm, data=dset)
                    
            # two D parm arrays
            twoDGroup = thisGroup.create_group('2D Parameters')
            self._addDataParametersTable(twoDGroup, 2)
            
            # get shape of 2D data (number of dimensions dynamic)
            twoDShape = []
            for indParm in indParmList:
                twoDShape.append(len(uniqueIndValueDict[indParm]))
            twoDShape.append(len(unique_times))
            
            dsetDict = {} # key = parm, value 2D dataset
            for parm in recLayout.dtype.names[len(self.requiredFields):]:
                if recLayout[parm][0] == 2:
                    dsetDict[parm] = numpy.zeros(twoDShape, dtype=table.dtype[parm])
                    if self.parmIsInt(parm):
                        dsetDict[parm][:] = self.missing_int
                    else:
                        dsetDict[parm][:] = self.missing
                    
            # precalculate the indices
            # time index
            time_indices = numpy.zeros((1, len(tableSubset.table)), int)
            times = tableSubset.table['ut1_unix']
            for i in range(len(unique_times)):
                t = unique_times[i]
                indices = numpy.argwhere(times == t)
                time_indices[0, indices] = i
            
            # ind parm indexes
            indParmIndexDict = {}
            for indParm in indParmList:
                values = tableSubset.table[indParm]
                indParmIndexDict[indParm] = numpy.zeros((1, len(tableSubset.table)), int)
                for i in range(len(uniqueIndValueDict[indParm])):
                    v = uniqueIndValueDict[indParm][i]
                    indices = numpy.argwhere(values == v)
                    indParmIndexDict[indParm][0, indices] = i
                
            # concatenate
            tableIndex = None
            for indParm in indParmList:
                if tableIndex is None:
                    tableIndex = indParmIndexDict[indParm]
                else:
                    tableIndex = numpy.concatenate((tableIndex, indParmIndexDict[indParm]), 0)
            tableIndex = numpy.concatenate((tableIndex, time_indices), 0)   
                    
            # set 2D parms
            for parm in recLayout.dtype.names[len(self.requiredFields):]:
                if recLayout[parm][0] == 2:
                    if len(indParmList) == 1:
                        dsetDict[parm][tableIndex[0], tableIndex[1]] = tableSubset.table[parm]
                    elif len(indParmList) == 2:
                        dsetDict[parm][tableIndex[0], tableIndex[1], tableIndex[2]] = tableSubset.table[parm]
                    elif len(indParmList) == 3:
                        dsetDict[parm][tableIndex[0], tableIndex[1], tableIndex[2], tableIndex[3]] = tableSubset.table[parm]
                    else:
                        raise ValueError('Can not handle more than 3 independent spatial parms - there are %i' % (len(indParmList)))
                        
            # write the datasets out
            for parm in recLayout.dtype.names[len(self.requiredFields):]:
                if recLayout[parm][0] == 2:
                    twoDGroup.create_dataset(parm, data=dsetDict[parm], compression='gzip')
                    
                    
                    
    def _createArrayLayout2(self):
        """_createArrayLayout2 will append an Array Layout to the Hdf5 file.  Called after dump.
        
        IOError raised if Array Layout already exists - this can only be called once
        """
        
        f = h5py.File(self._fullFilename, 'a')
        # get info from recarrays that already exist
        table = f['Data']['Table Layout']
        recLayout = f['Metadata']['_record_layout']
        metadataGroup = f['Metadata']
        
        # inputs
        indParmList = self.getIndSpatialParms()
        
        if "Array Layout" in list(f['Data'].keys()):
            raise IOError('Array Layout already created - this can only be created once.')
        
        # update metadata now that file finished
        self._writeHdf5Metadata(f, refreshCatHeadTimes=True)
        
        if self._skipArray:
            f.close()
            return
        
        # now that self._arrDict is competely filled out, create a similar dict, except that
        # all sets are replaced by ordered python arrays
        total_allowed_records = 0 # make sure all ind parameters declared by checking that the product
                                  # of all the ind parm value lengths time the number of times is equal
                                  # to or greater than the number of total records
        arrDict = {}
        for key in list(self._arrDict.keys()):
            total_ind_parm_lens = []
            thisDict = self._arrDict[key]
            arrDict[key] = {}
            for key2 in list(thisDict.keys()):
                thisSet = thisDict[key2]
                # convert to ordered numpy array
                thisList = list(thisSet)
                thisList.sort()
                total_ind_parm_lens.append(len(thisList))
                if self._madParmObj.isInteger(key2):
                    data = numpy.array(thisList, dtype=numpy.int64)
                elif self._madParmObj.isString(key2):
                    strLen = self._madParmObj.getStringLen(key2)
                    data = numpy.array(thisList, dtype=numpy.dtype('S%i' % (strLen)))
                else:
                    data = numpy.array(thisList, dtype=numpy.float64)
                arrDict[key][key2] = data
                
            # add the max number of records for this group
            tmp = total_ind_parm_lens[0]
            for v in total_ind_parm_lens[1:]:
                tmp *= v
            total_allowed_records += tmp
            
            # protect against too many ind parm combinations (too sparse an array)
            total_ind_combos = total_ind_parm_lens[1]
            for v in total_ind_parm_lens[2:]:
                total_ind_combos *= v
            if total_ind_combos > 1000000:
                print(('Skipping array creation since %i independent parm combinations would create too big an array' % (total_ind_combos)))
                f.close()
                return
            
        if len(table) > total_allowed_records:
            raise ValueError('Found %i lines in table, but values of times and ind parms %s allow maximum of %i values in file %s' % \
                (len(table), str(indParmList), total_allowed_records, self._fullFilename))
        
        # add "Parameters Used to Split Array Data" to Metadata
        if not self._arraySplitParms == []:
            arrSplitParmDesc = []
            longestMnemStr = 0
            longestDescStr = 0
            for arrSplitParm in self._arraySplitParms:
                if len(arrSplitParm) > longestMnemStr:
                    longestMnemStr = len(arrSplitParm)
                arrSplitParmDesc.append(self._madParmObj.getSimpleParmDescription(arrSplitParm))
                if len(arrSplitParmDesc[-1]) > longestDescStr:
                    longestDescStr = len(arrSplitParmDesc[-1])
            arrSplitArr = numpy.recarray((len(self._arraySplitParms),),
                                         dtype = [('mnemonic', '|S%i' % (longestMnemStr)),
                                                  ('description', '|S%i' % (longestDescStr))])
            for i, arrSplitParm in enumerate(self._arraySplitParms):
                arrSplitArr[i]['mnemonic'] = arrSplitParm
                arrSplitArr[i]['description'] = arrSplitParmDesc[i]
            
            metadataGroup.create_dataset('Parameters Used to Split Array Data', data=arrSplitArr)
            

        arrGroup = f['Data'].create_group("Array Layout")
        
        # stage 1 - write all needed tables with nan values
        for key in list(arrDict.keys()):
            if key != '':
                groupName = self._getGroupName(key)
                thisGroup = arrGroup.create_group(groupName)
            else:
                thisGroup = arrGroup # no subgroups needed
                
            self._addLayoutDescription(thisGroup)
                
            """thisDict is dict of key = 'ut1_unix' and ind 2d parm names (possibly minus arraySplitParms), values
                = ordered numpy array of all unique values"""
            thisDict = arrDict[key] 
                                      
            unique_times = thisDict['ut1_unix']
            
            ts_dset = thisGroup.create_dataset("timestamps", data=unique_times)
            for indParm in indParmList:
                if indParm in self._arraySplitParms:
                    # not needed
                    continue
                dataset = thisDict[indParm]
                thisGroup.create_dataset(indParm, data=dataset)
                
            # one D parm arrays
            oneDGroup = thisGroup.create_group('1D Parameters')
            self._addDataParametersTable(oneDGroup, 1)
            for parm in recLayout.dtype.names[len(self.requiredFields):]:
                if recLayout[parm][0] == 1:
                    if self._madParmObj.isInteger(parm):
                        dset = numpy.zeros((len(unique_times),), dtype=numpy.int64)
                        dset[:] = numpy.iinfo(numpy.int64).min
                    elif self._madParmObj.isString(parm):
                        strLen = self._madParmObj.getStringLen(parm)
                        dset = numpy.zeros((len(unique_times),), dtype=numpy.dtype(("S" + str(strLen))))
                    else:
                        dset = numpy.zeros((len(unique_times),), dtype=numpy.float64)
                        dset[:] = numpy.nan
                    oneDGroup.create_dataset(parm, data=dset)
            
            # two D parm arrays
            twoDGroup = thisGroup.create_group('2D Parameters')
            self._addDataParametersTable(twoDGroup, 2)
            
            # get shape of 2D data (number of dimensions dynamic)
            twoDShape = []
            for indParm in indParmList:
                if indParm in self._arraySplitParms:
                    # not needed
                    continue
                twoDShape.append(len(thisDict[indParm]))
            twoDShape.append(len(unique_times))
            for parm in recLayout.dtype.names[len(self.requiredFields):]:
                if recLayout[parm][0] == 2:
                    if self._madParmObj.isInteger(parm):
                        dset = numpy.zeros(twoDShape, dtype=numpy.int64)
                        dset[:] = numpy.iinfo(numpy.int64).min
                    elif self._madParmObj.isString(parm):
                        strLen = self._madParmObj.getStringLen(parm)
                        dset = numpy.zeros(twoDShape, dtype=numpy.dtype(("S" + str(strLen))))
                    else:
                        dset = numpy.zeros(twoDShape, dtype=numpy.float64)
                        dset[:] = numpy.nan
                    twoDGroup.create_dataset(parm, data=dset)
                    
        # flush file
        f.close()
        f = h5py.File(self._fullFilename, 'a')
        table = f['Data']['Table Layout']
        recLayout = f['Metadata']['_record_layout']
        
        # now loop through Table Layout and populate all the 1 and 2 d arrays
        step = 10 # number of records to load at once
        total_steps = int(len(self._recIndexList) / step)
        if total_steps * step < len(self._recIndexList):
            total_steps += 1
        for i in range(total_steps):
            startTimeIndex = i*step
            if (i+1)*step < len(self._recIndexList) - 1:
                endTimeIndex = (i+1)*step - 1
            else:
                endTimeIndex = len(self._recIndexList) - 1
            table_data = table[self._recIndexList[startTimeIndex][0]:self._recIndexList[endTimeIndex][1]]
            # loop through all groups
            for key in list(arrDict.keys()):
                tableSubset = _TableSubset(self._arraySplitParms, key, table_data)
                # its possible no data in this slice for this subset
                if len(tableSubset.table) == 0:
                    continue
                
                timestamps = arrDict[key]['ut1_unix']

                # get index of first and last time found
                first_ut1_unix = tableSubset.table[0]['ut1_unix']
                last_ut1_unix = tableSubset.table[-1]['ut1_unix']
                time_index_1 = numpy.searchsorted(timestamps, first_ut1_unix)
                time_index_2 = numpy.searchsorted(timestamps, last_ut1_unix) + 1
                groupName = tableSubset.getGroupName()
                # get shape of 2D data (number of dimensions dynamic)
                twoDShape = []
                for indParm in indParmList:
                    if indParm in self._arraySplitParms:
                        # not needed
                        continue
                    twoDShape.append(len(arrDict[key][indParm]))
                twoDShape.append(time_index_2 - time_index_1)
                # ind parm indexes
                indParmIndexDict = {}
                for indParm in indParmList:
                    if indParm in self._arraySplitParms:
                        # not needed
                        continue
                    values = tableSubset.table[indParm]
                    indParmIndexDict[indParm] = numpy.zeros((len(tableSubset.table),), int)
                    for i in range(len(arrDict[key][indParm])):
                        v = arrDict[key][indParm][i]
                        indices = numpy.argwhere(values == v)
                        indParmIndexDict[indParm][indices] = i
                    
                # finally time dimension
                values = tableSubset.table['ut1_unix']
                timeIndices = numpy.zeros((len(tableSubset.table),), int)
                thisTimestampArr = numpy.unique(tableSubset.table['ut1_unix'])
                for i in range(len(thisTimestampArr)):
                    v = thisTimestampArr[i]
                    indices = numpy.argwhere(values == v)
                    timeIndices[indices] = i

                # concatenate
                tableIndex = []
                for indParm in indParmList:
                    if indParm in self._arraySplitParms:
                        # not needed
                        continue
                    tableIndex.append(indParmIndexDict[indParm])
                tableIndex.append(timeIndices)
                for parm in recLayout.dtype.names[len(self.requiredFields):]:
                    if recLayout[parm][0] == 1:
                        dset = tableSubset.table[parm][tableSubset.oneDIndices]
                        if not groupName is None:
                            f['Data']['Array Layout'][groupName]['1D Parameters'][parm][time_index_1:time_index_2] = dset
                        else:
                            f['Data']['Array Layout']['1D Parameters'][parm][time_index_1:time_index_2] = dset
                    elif recLayout[parm][0] == 2:
                        if self._madParmObj.isInteger(parm):
                            dset2 = numpy.zeros(tuple(twoDShape), dtype=numpy.int64)
                            dset2[:] = numpy.iinfo(numpy.int64).min
                        elif self._madParmObj.isString(parm):
                            strLen = self._madParmObj.getStringLen(parm)
                            dset2 = numpy.zeros(tuple(twoDShape), dtype=numpy.dtype(("S" + str(strLen))))
                            dset2[:] = ''
                        else:
                            dset2 = numpy.zeros(tuple(twoDShape), dtype=numpy.float64)
                            dset2[:] = numpy.nan
                        dset2[tuple(tableIndex)] = tableSubset.table[parm]
                        
                        if not groupName is None:
                            fdata = f['Data']['Array Layout'][groupName]['2D Parameters'][parm]
                        else:
                            fdata = f['Data']['Array Layout']['2D Parameters'][parm]
                            
                        if len(indParmList) - self._num2DSplit == 1:
                            fdata[:,time_index_1:time_index_2] = dset2
                        elif len(indParmList) - self._num2DSplit == 2:
                            fdata[:,:,time_index_1:time_index_2] = dset2
                        elif len(indParmList) - self._num2DSplit == 3:
                            fdata[:,:,:,time_index_1:time_index_2] = dset2
                        elif len(indParmList) - self._num2DSplit == 4:
                            fdata[:,:,:,:,time_index_1:time_index_2] = dset2
                        elif len(indParmList) - self._num2DSplit == 5:
                            fdata[:,:,:,:,:,time_index_1:time_index_2] = dset2
                        else:
                            raise ValueError('Can not handle more than 5 independent spatial parms - there are %i' % (len(indParmList)))
                        
        f.close()
            
                    
    def _writeNetCDF4(self, f, arraySplittingParms):
        """_writeNetCDF4 will write to a netCDF4 file f
        
        arraySplittingParms - a list of parameters as mnemonics used to split
            arrays into subarrays.  For example, beamcode would split data with separate beamcodes
            into separate arrays. The number of separate arrays will be up to the product of the number of 
            unique values found for each parameter, with the restriction that combinations with no records will
            not create a separate array.
        
        """
        # create merged datasets table and recLayout
        datasetList = []
        recordList = []
            
        for rec in self._privList:
            
            if rec.getType() == 'data':
                datasetList.append(rec._dataset)
                if len(recordList) == 0:
                    recordList.append(rec._recordSet)
                
            elif rec.getType() == 'catalog':
                f.catalog_text = rec.getText()
                
            elif rec.getType() == 'header':
                f.header_text = rec.getText()
                
        if len(datasetList) == 0:
            raise IOError('No data records in file')
        
        table = numpy.concatenate(datasetList)
        recLayout = numpy.concatenate(recordList)
        
        if self._experimentParameters is None:
            self.refreshSummary()
        
        # write Experiment Parameters
        for i in range(len(self._experimentParameters)):
            name = self._experimentParameters['name'][i]
            # make text acceptable attribute names
            if type(name) in (bytes, numpy.bytes_):
                name = name.replace(b' ', b'_')
                name = name.replace(b'(s)', b'')
            else:
                name = name.replace(' ', '_')
                name = name.replace('(s)', '')
            f.setncattr(name, self._experimentParameters['value'][i])
        
        indParmList = self.getIndSpatialParms()
        
        # add "Parameters Used to Split Array Data" to Metadata
        if len(arraySplittingParms) > 0:
            arrSplitParmDesc = ''
            for arrSplitParm in arraySplittingParms:
                arrSplitParmDesc += '%s: ' % (arrSplitParm)
                arrSplitParmDesc += '%s' % (self._madParmObj.getSimpleParmDescription(arrSplitParm))
                if arrSplitParm != arraySplittingParms[-1]:
                    arrSplitParmDesc += ' -- '
            f.parameters_used_to_split_data = arrSplitParmDesc
            
        
        arraySplittingList = [] # list of lists of all existing values for each array splitting parm
        for parm in arraySplittingParms:
            if type(parm) in (bytes, numpy.bytes_):
                parm = parm.decode('utf-8')
            arraySplittingList.append(numpy.unique(table[parm]))
        
        tableSubsets = []
        for combo in itertools.product(*arraySplittingList):
            tableSubsets.append(_TableSubset(arraySplittingParms, combo, table))
        
        for tableSubset in tableSubsets:
            uniqueIndValueDict = {}
            for indParm in indParmList:
                uniqueIndValueDict[indParm] = numpy.unique(tableSubset.table[indParm])
            if not self._useRecno:
                unique_times = numpy.unique(tableSubset.table['ut1_unix'])
            else:
                unique_times = numpy.unique(tableSubset.table['recno'])
            group_name = tableSubset.getGroupName()
            if group_name != None:
                group_name = group_name.strip().replace(' ', '_')
                thisGroup = f.createGroup(group_name)
            else:
                thisGroup = f # no splitting, so no subgroup needed
            # next step - create dimensions
            dims = []
            if not self._useRecno:
                thisGroup.createDimension("timestamps", len(unique_times))
                timeVar = thisGroup.createVariable("timestamps", 'f8', ("timestamps",),
                                                   zlib=True)
                timeVar.units = 'Unix seconds'
                timeVar.description = 'Number of seconds since UT midnight 1970-01-01'
                timeVar[:] = unique_times
                dims.append("timestamps")
            else:
                thisGroup.createDimension("record_nums", len(unique_times))
                timeVar = thisGroup.createVariable("record_nums", 'f8', ("record_nums",),
                                                   zlib=True)
                timeVar.units = 'N/A'
                timeVar.description = 'Record number'
                timeVar[:] = unique_times
                dims.append("record_nums")
            for indParm in indParmList:
                this_name = indParm
                if this_name[0] == '-':
                    this_name = 'neg' + this_name
                thisGroup.createDimension(indParm, len(uniqueIndValueDict[indParm]))
                if self._madParmObj.isInteger(indParm):
                    thisVar = thisGroup.createVariable(this_name, 'i8', (indParm,), zlib=True)
                elif self._madParmObj.isString(indParm):
                    thisVar = thisGroup.createVariable(this_name, self.getStringFormat(indParm), (indParm,), zlib=True)
                else:
                    thisVar = thisGroup.createVariable(this_name, 'f8', (indParm,), zlib=True)
                thisVar[:] = uniqueIndValueDict[indParm]
                thisVar.units = self._madParmObj.getParmUnits(indParm)
                thisVar.description = self._madParmObj.getSimpleParmDescription(indParm)
                dims.append(indParm)
                
            # create one and two D parm arrays, set 1D
            twoDVarDict = {} # key = parm name, value = netCDF4 variable
            name_list = list(recLayout.dtype.names[len(self.requiredFields):])
            if self._useRecno:
                name_list.append('ut1_unix')
            for parm in name_list:
                this_name = parm
                if this_name[0] == '-':
                    this_name = 'neg' + this_name
                if recLayout[parm][0] == 1:
                    dset = tableSubset.table[parm][tableSubset.oneDIndices]
                    if self.parmIsInt(parm):
                        oneDVar = thisGroup.createVariable(this_name, 'i8', (dims[0],), zlib=True)
                    elif self.parmIsString(parm):
                        oneDVar = thisGroup.createVariable(this_name, self.getStringFormat(parm), (dims[0],),
                                                           zlib=True)
                    else: # float
                        oneDVar = thisGroup.createVariable(this_name, 'f8', (dims[0],), zlib=True)
                    oneDVar.units = self._madParmObj.getParmUnits(parm)
                    oneDVar.description = self._madParmObj.getSimpleParmDescription(parm)
                    try:
                        oneDVar[:] = dset
                    except:
                        raise ValueError('There may be an issue with array splitting because more records than times')
                elif recLayout[parm][0] == 2:
                    if self.parmIsInt(parm):
                        twoDVarDict[parm] = thisGroup.createVariable(this_name, 'i8', dims, zlib=True)
                    elif self.parmIsString(parm):
                        twoDVarDict[parm] = thisGroup.createVariable(this_name, self.getStringFormat(parm), dims, zlib=True)
                    else:
                        twoDVarDict[parm] = thisGroup.createVariable(this_name, 'f8', dims, zlib=True)
                    twoDVarDict[parm].units = self._madParmObj.getParmUnits(parm)
                    twoDVarDict[parm].description = self._madParmObj.getSimpleParmDescription(parm)
                    
            # two D parm arrays
            
            # get shape of 2D data (number of dimensions dynamic)
            twoDShape = []
            twoDShape.append(len(unique_times))
            for indParm in indParmList:
                twoDShape.append(len(uniqueIndValueDict[indParm]))
            
            dsetDict = {} # key = parm, value 2D dataset
            for parm in recLayout.dtype.names[len(self.requiredFields):]:
                if recLayout[parm][0] == 2:
                    dsetDict[parm] = numpy.zeros(twoDShape, dtype=table.dtype[parm])
                    if self.parmIsInt(parm):
                        dsetDict[parm][:] = self.missing_int
                    else:
                        dsetDict[parm][:] = self.missing
                    
            # precalculate the indices
            # time index
            time_indices = numpy.zeros((1, len(tableSubset.table)), int)
            if not self._useRecno:
                times = tableSubset.table['ut1_unix']
            else:
                times = tableSubset.table['recno']
            for i in range(len(unique_times)):
                t = unique_times[i]
                indices = numpy.argwhere(times == t)
                time_indices[0, indices] = i
            
            # ind parm indexes
            indParmIndexDict = {}
            for indParm in indParmList:
                values = tableSubset.table[indParm]
                indParmIndexDict[indParm] = numpy.zeros((1, len(tableSubset.table)), int)
                for i in range(len(uniqueIndValueDict[indParm])):
                    v = uniqueIndValueDict[indParm][i]
                    indices = numpy.argwhere(values == v)
                    indParmIndexDict[indParm][0, indices] = i
                
            # concatenate
            tableIndex = time_indices
            for indParm in indParmList:
                tableIndex = numpy.concatenate((tableIndex, indParmIndexDict[indParm]), 0)
                    
            # set 2D parms
            for parm in recLayout.dtype.names[len(self.requiredFields):]:
                if recLayout[parm][0] == 2:
                    if len(indParmList) == 1:
                        dsetDict[parm][tableIndex[0], tableIndex[1]] = tableSubset.table[parm]
                    elif len(indParmList) == 2:
                        dsetDict[parm][tableIndex[0], tableIndex[1], tableIndex[2]] = tableSubset.table[parm]
                    elif len(indParmList) == 3:
                        dsetDict[parm][tableIndex[0], tableIndex[1], tableIndex[2], tableIndex[3]] = tableSubset.table[parm]
                    elif len(indParmList) == 0:
                        continue
                    else:
                        raise ValueError('Can not handle more than 3 independent spatial parms - there are %i' % (len(indParmList)))
                        
            # write the datasets out
            for parm in recLayout.dtype.names[len(self.requiredFields):]:
                if recLayout[parm][0] == 2:
                    if parm in twoDVarDict:
                        if len(indParmList) == 1:
                            twoDVarDict[parm][:,:] = dsetDict[parm]
                        elif len(indParmList) == 2:
                            twoDVarDict[parm][:,:,:] = dsetDict[parm]
                        elif len(indParmList) == 3:
                            twoDVarDict[parm][:,:,:,:] = dsetDict[parm]
                        
                        
                        
    def _firstDumpNetCDF4(self, f, parmIndexDict):
        """_firstDumpNetCDF4 will dump initial data to a netCDF4 file f.  Called via dump
        
            
        parmIndexDict - is a dictionary with key = timestamps and ind spatial parm names,
            value = dictionary of keys = unique values, value = index of that value. Can only be used when
            arraySplittingParms == []
        
        """
        # create merged datasets table and recLayout
        datasetList = []
        recordList = []
            
        for rec in self._privList:
            
            if rec.getType() == 'data':
                datasetList.append(rec._dataset)
                if len(recordList) == 0:
                    recordList.append(rec._recordSet)
                
            elif rec.getType() == 'catalog':
                f.catalog_text = rec.getText()
                
            elif rec.getType() == 'header':
                f.header_text = rec.getText()
                
        if len(datasetList) == 0:
            raise IOError('No data records in file')
        
        table = numpy.concatenate(datasetList)
        recLayout = numpy.concatenate(recordList)
        
        if self._experimentParameters is None:
            self.refreshSummary()
        
        # write Experiment Parameters
        for i in range(len(self._experimentParameters)):
            name = self._experimentParameters['name'][i]
            # make text acceptable attribute names
            if type(name) in (bytes, numpy.bytes_):
                name = name.replace(b' ', b'_')
                name = name.replace(b'(s)', b'')
            else:
                name = name.replace(' ', '_')
                name = name.replace('(s)', '')
            f.setncattr(name, self._experimentParameters['value'][i])
        
        indParmList = self.getIndSpatialParms()
        
        uniqueIndValueDict = {}
        for indParm in indParmList:
            uniqueIndValueDict[indParm] = numpy.array(list(parmIndexDict[indParm].keys()))
        unique_times = numpy.array(list(parmIndexDict['ut1_unix'].keys()))
        if not self._useRecno:
            unique_times = numpy.array(list(parmIndexDict['ut1_unix'].keys()))
        else:
            unique_times = numpy.array(list(parmIndexDict['recno'].keys()))
        thisGroup = f # no splitting, so no subgroup needed
        # next step - create dimensions
        dims = []
        
        if not self._useRecno:
            thisGroup.createDimension("timestamps", len(unique_times))
            timeVar = thisGroup.createVariable("timestamps", 'f8', ("timestamps",),
                                                   zlib=True)
            timeVar.units = 'Unix seconds'
            timeVar.description = 'Number of seconds since UT midnight 1970-01-01'
            timeVar[:] = unique_times
            dims.append("timestamps")
        else:
            thisGroup.createDimension("record_nums", len(unique_times))
            timeVar = thisGroup.createVariable("record_nums", 'f8', ("record_nums",),
                                                   zlib=True)
            timeVar.units = 'N/A'
            timeVar.description = 'Record number'
            timeVar[:] = unique_times
            dims.append("record_nums")
            
        for indParm in indParmList:
            this_name = indParm
            if this_name[0] == '-':
                this_name = 'neg' + this_name
            thisGroup.createDimension(indParm, len(uniqueIndValueDict[indParm]))
            if self._madParmObj.isInteger(indParm):
                thisVar = thisGroup.createVariable(this_name, 'i8', (indParm,), zlib=False)
            elif self._madParmObj.isString(indParm):
                thisVar = thisGroup.createVariable(this_name, self.getStringFormat(indParm), (indParm,), zlib=False)
            else:
                thisVar = thisGroup.createVariable(this_name, 'f8', (indParm,), zlib=False)
            thisVar[:] = uniqueIndValueDict[indParm]
            thisVar.units = self._madParmObj.getParmUnits(indParm)
            thisVar.description = self._madParmObj.getSimpleParmDescription(indParm)
            dims.append(indParm)
            
        # create one and two D parm arrays, set 1D
        twoDVarDict = {} # key = parm name, value = netCDF4 variable
        name_list = list(recLayout.dtype.names[len(self.requiredFields):])
        if self._useRecno:
            name_list.append('ut1_unix')
        for parm in name_list:
            this_name = parm
            if this_name[0] == '-':
                this_name = 'neg' + this_name
            if recLayout[parm][0] == 1:
                dset = table[parm][:]
                if self.parmIsInt(parm):
                    oneDVar = thisGroup.createVariable(this_name, 'i8', (dims[0],), zlib=False)
                elif self.parmIsString(parm):
                    oneDVar = thisGroup.createVariable(this_name, self.getStringFormat(parm), (dims[0],),
                                                       zlib=False)
                else: # float
                    oneDVar = thisGroup.createVariable(this_name, 'f8', (dims[0],), zlib=False)
                oneDVar.units = self._madParmObj.getParmUnits(parm)
                oneDVar.description = self._madParmObj.getSimpleParmDescription(parm)
                lastTS = 0.0
                for i, ts in enumerate(table['ut1_unix']):
                    if ts != lastTS:
                        # set it
                        oneDVar[parmIndexDict['ut1_unix'][ts]] = dset[i]
                        lastTS = ts

            elif recLayout[parm][0] == 2:
                if self.parmIsInt(parm):
                    twoDVarDict[parm] = thisGroup.createVariable(this_name, 'i8', dims, zlib=False)
                elif self.parmIsString(parm):
                    twoDVarDict[parm] = thisGroup.createVariable(this_name, self.getStringFormat(parm), dims, zlib=False)
                else:
                    twoDVarDict[parm] = thisGroup.createVariable(this_name, 'f8', dims, zlib=False, fill_value=numpy.nan)
                twoDVarDict[parm].units = self._madParmObj.getParmUnits(parm)
                twoDVarDict[parm].description = self._madParmObj.getSimpleParmDescription(parm)
                
                
        # set 2D parms
        for i in range(len(table)):
            parmIndices = [parmIndexDict['ut1_unix'][table['ut1_unix'][i]]] 
                    
            for indParm in indParmList:
                item = table[indParm][i]
                if type(item) in (bytes, numpy.bytes_):
                    item = item.decode('utf-8')
                parmIndices.append(parmIndexDict[indParm][item])
                
            for parm in recLayout.dtype.names[len(self.requiredFields):]:
                if recLayout[parm][0] == 2:
                
                    if len(indParmList) == 1:
                        twoDVarDict[parm][parmIndices[0], parmIndices[1]] = table[parm][i]
                    elif len(indParmList) == 2:
                        twoDVarDict[parm][parmIndices[0], parmIndices[1], parmIndices[2]] = table[parm][i]
                    elif len(indParmList) == 3:
                        twoDVarDict[parm][parmIndices[0], parmIndices[1], parmIndices[2], parmIndices[3]] = table[parm][i]
                    elif len(indParmList) == 0:
                        continue
                    else:
                        raise ValueError('Can not handle more than 3 independent spatial parms - there are %i' % (len(indParmList)))

                    
                    
    def _appendNetCDF4(self, f, parmIndexDict):
        """_appendNetCDF4 will dump appended data to a netCDF4 file f. Called via dump
        
            
        parmIndexDict - is a dictionary with key = timestamps and ind spatial parm names,
            value = dictionary of keys = unique values, value = index of that value. Can only be used when
            arraySplittingParms == []

        """
        # create merged datasets table and recLayout
        datasetList = []
        recordList = []
            
        for rec in self._privList:
            
            if rec.getType() == 'data':
                datasetList.append(rec._dataset)
                if len(recordList) == 0:
                    recordList.append(rec._recordSet)
                
            elif rec.getType() == 'catalog':
                f.catalog_text = rec.getText()
                
            elif rec.getType() == 'header':
                f.header_text = rec.getText()
                
        if len(datasetList) == 0:
            raise IOError('No data records in file')
        
        table = numpy.concatenate(datasetList)
        recLayout = numpy.concatenate(recordList)
        
        
        indParmList = self.getIndSpatialParms()
        
        uniqueIndValueDict = {}
        for indParm in indParmList:
            uniqueIndValueDict[indParm] = numpy.array(list(parmIndexDict[indParm].keys()))
        if not self._useRecno:
            unique_times = numpy.array(list(parmIndexDict['ut1_unix'].keys()))
            thisGroup = f # no splitting, so no subgroup needed
            # next step - create dimensions
            dims = []
            timeVar = thisGroup.variables["timestamps"]
            dims.append("timestamps")
            for indParm in indParmList:
                thisVar = thisGroup.variables[indParm]
                dims.append(indParm)
        else:
            unique_times = numpy.array(list(parmIndexDict['recno'].keys()))
            thisGroup = f # no splitting, so no subgroup needed
            # next step - create dimensions
            dims = []
            timeVar = thisGroup.variables["recno"]
            dims.append("recno")
            for indParm in indParmList:
                thisVar = thisGroup.variables[indParm]
                dims.append(indParm)
            
        # create one and two D parm arrays, set 1D
        twoDVarDict = {} # key = parm name, value = netCDF4 variable
        name_list = list(recLayout.dtype.names[len(self.requiredFields):])
        if self._useRecno:
            name_list.append('ut1_unix')
        for parm in name_list:
            if recLayout[parm][0] == 1:
                dset = table[parm][:]
                oneDVar = thisGroup.variables[parm]
                lastTS = 0.0
                if not self._useRecno:
                    for i, ts in enumerate(table['ut1_unix']):
                        if ts != lastTS:
                            # set it
                            oneDVar[parmIndexDict['ut1_unix'][ts]] = dset[i]
                            lastTS = ts
                else:
                    for i, ts in enumerate(table['recno']):
                        if ts != lastTS:
                            # set it
                            oneDVar[parmIndexDict['recno'][ts]] = dset[i]
                            lastTS = ts

            elif recLayout[parm][0] == 2:
                twoDVarDict[parm] = thisGroup.variables[parm]
                
                
        # set 2D parms
        for parm in recLayout.dtype.names[len(self.requiredFields):]:
            if recLayout[parm][0] == 2:
                for i in range(len(table)):
                    if not self._useRecno:
                        parmIndices = [parmIndexDict['ut1_unix'][table['ut1_unix'][i]]] 
                    else:
                        parmIndices = [parmIndexDict['recno'][table['recno'][i]]] 
                    for indParm in indParmList:
                        item = table[indParm][i]
                        if type(item) in (bytes, numpy.bytes_):
                            item = item.decode('utf-8')
                        parmIndices.append(parmIndexDict[indParm][item])
                    if len(indParmList) == 1:
                        twoDVarDict[parm][parmIndices[0], parmIndices[1]] = table[parm][i]
                    elif len(indParmList) == 2:
                        twoDVarDict[parm][parmIndices[0], parmIndices[1], parmIndices[2]] = table[parm][i]
                    elif len(indParmList) == 3:
                        twoDVarDict[parm][parmIndices[0], parmIndices[1], parmIndices[2], parmIndices[3]] = table[parm][i]
                    elif len(indParmList) == 0:
                        continue
                    else:
                        raise ValueError('Can not handle more than 3 independent spatial parms - there are %i' % (len(indParmList)))
                    
                    
    def _addLayoutDescription(self, group):
        """_addLayoutDescription added a Layout Description dataset to h5py group
        """
        indSpatialParms = self.getIndSpatialParms()
        layoutDesc = self._getLayoutDescription() % (str(indSpatialParms),
                                                     str(indSpatialParms),
                                                     1+len(indSpatialParms),
                                                     len(indSpatialParms),
                                                     str(indSpatialParms),
                                                     str(indSpatialParms))
        LayoutDescription = layoutDesc.split('\n')
        # create a recarray to hold this text
        textArr = numpy.recarray((len(LayoutDescription),), dtype=[('Layout Description', h5py.special_dtype(vlen=str))])
        for i in range(len(LayoutDescription)):
            textArr['Layout Description'][i] = LayoutDescription[i]
            
        group.create_dataset('Layout Description', data=textArr)
        
                    
    
    def _getLayoutDescription(self):
        """_getLayoutDescription returns a description of the layout selected.
        
        Returns: 
            LayoutDescription: A list of strings summarizing the Layout Description

        Affects: Nothing

        Exceptions: None
        """
        
        LayoutDescription = """
                This data layout contains reshaped data from the Table Layout. The reshaped data is stored as an array, with time and
                the independent spatial parameters (%s) in different dimensions. It creates an array for each parameter found in file.
                
                This layout contains:
                - "1D parameters" group: contains one 1D-array for each 1d parameter
                                  stored in the file. Time-dependent only parameters.
                - "2D parameters" group: contains one 2D-array for each 2d parameter
                                  stored in the file. Time and %s are independent parameters.
                                  Every 2D array has %i dimensions - one for time, and %i for
                                  the independent spatial parameters (%s).
                - timestamps:     Time vector in seconds from 1/1/1970.
                
                - %s :          The independent spatial parameters for this file"""
                
        return(LayoutDescription)
        
        
        
        
    def _addDataParametersTable(self, group, dim=None):
        """_addDataParametersTable adds the "Data Parameters" table to the h5py Group group if any parameters found
        
        Inputs:
        
            group - the h5py Group to add the dataset to
            
            dim - if None, include all parameters. If 1 or 2, just include non-required 1 or 2 D parms
        """
        if dim not in (None, 1, 2):
            raise ValueError('dim must be in (None, 1, 2), not <%s>' % (str(dim)))
        
        # this first pass is just to set the maximum length of all the strings
        longestMnemStr = 0
        longestDescStr = 0
        longestUnitsStr = 0
        longestCategoryStr = 0
        count = 0
        for i, parm in enumerate(self._tableDType.names):
            if dim in (1,2) and i < len(self.requiredFields):
                # skipping default parms
                continue
            if dim in (1,2):
                if self.getParmDim(parm) != dim:
                    continue
            count += 1
            if len(self._madParmObj.getParmMnemonic(parm)) > longestMnemStr:
                longestMnemStr = len(self._madParmObj.getParmMnemonic(parm))
            if len(self._madParmObj.getSimpleParmDescription(parm)) > longestDescStr:
                longestDescStr = len(self._madParmObj.getSimpleParmDescription(parm))
            if len(self._madParmObj.getParmUnits(parm)) > longestUnitsStr:
                longestUnitsStr = len(self._madParmObj.getParmUnits(parm))
            if len(self._madParmObj.getParmCategory(parm)) > longestCategoryStr:
                longestCategoryStr = len(self._madParmObj.getParmCategory(parm))
        
        if count == 0: # no parms to add
            return
        
        parmArr = numpy.recarray((count,),
                                 dtype = [('mnemonic', '|S%i' % (longestMnemStr)),
                                          ('description', '|S%i' % (longestDescStr)),
                                          ('isError', 'int'),
                                          ('units', '|S%i' % (longestUnitsStr)),
                                          ('category', '|S%i' % (longestCategoryStr))])
        
        # set all the values
        count = 0
        for i, parm in enumerate(self._tableDType.names):
            if dim in (1,2) and i < len(self.requiredFields):
                # skipping default parms
                continue
            if dim in (1,2):
                if self.getParmDim(parm) != dim:
                    continue
                
            parmArr['mnemonic'][count] = self._madParmObj.getParmMnemonic(parm)
            parmArr['description'][count] = self._madParmObj.getSimpleParmDescription(parm)
            parmArr['isError'][count] = self._madParmObj.isError(parm)
            parmArr['units'][count] = self._madParmObj.getParmUnits(parm)
            parmArr['category'][count] = self._madParmObj.getParmCategory(parm)
            count += 1
            
        group.create_dataset("Data Parameters", data=parmArr)
        
        
    def _writeRecordLayout(self, metadataGroup):
        """_writeRecordLayout adds the "_record_layout" table to the Metadata group metadataGroup if needed
        """
        tableName = '_record_layout'
        
        if self._recDset is None:
            raise IOError('self._recDset not yet specified')
        
        if tableName not in list(metadataGroup.keys()):
            dset = metadataGroup.create_dataset(tableName, data=self._recDset)
            dset.attrs['description'] = 'This is meant to be internal data.  For each Madrigal record and parameter, it has a 2 if its a 2D parameter, 1 if its a 1D parameter, and 0 if there is no data.'
            
            
            
    def _verifyFormat(self, tableDset, recDset):
        """verifyFormat raises an exception if any problem with the Hdf5 input file.
        
        Inputs:
            tableDset - dataset from hdfFile["Data"]["Table Layout"]
            recDset - dataset from hdfFile["Metadata"]["_record_layout"]
        
        Rules:  1. self._tableDset must start with  int columns 'year', 'month', 'day', 'hour', 'min', 'sec', 
                    'recno', 'kindat', 'kinst' and float columns 'ut1_unix', 'ut2_unix'
                2. The len of self._recDset must be 1 and must start with the same columns
        """
        
        for i, requiredField in enumerate(self.requiredFields):
            if requiredField != tableDset.dtype.names[i]:
                raise IOError('Field %s not found in table dset of Hdf5 file %s' % (requiredField, str(self._fullFilename)))
            if requiredField != self._recDset.dtype.names[i]:
                raise IOError('Field %s not found in record dset of Hdf5 file %s' % (requiredField, str(self._fullFilename)))
            
        if len(recDset) != 1:
            raise IOError('recDset must have len 1, not' % (len(recDset)))
        
        for field in  self._recDset.dtype.names:
            if self._recDset[0][field] not in (1,2,3):
                raise IOError('For field %s, got illegal recordset value %s' % (field, str(self._recDset[0][field])))
       
       
    def _appendCatalogRecs(self, expNotesDataset):
        """_appendCatalogRecs will append 0 or more MadrigalCatalogRecords to self._privList based
        on the contents in h5py dataset expNotesDataset
        """
        start_delimiter = 'Catalog information from record'
        end_delimiter = 'Header information from record'
        in_catalog = False
        catalog_text = ''
        start_found = False
        if len(self._kinstList) > 0:
            kinst = self._kinstList[0]
        else:
            kinst = None
        for line in expNotesDataset:
            line = line[0]
            if type(line) in (bytes, numpy.bytes_):
                line = line.decode('utf8')
            if not in_catalog and line.find(start_delimiter) != -1:
                in_catalog = True
                continue
            if in_catalog and (line.find(end_delimiter) != -1 or line.find(start_delimiter) != -1):
                start_found = False
                if len(catalog_text) > 0:
                    self._privList.append(MadrigalCatalogRecord(kinst,None,None,None,None,
                                                                None,None,None,None,None,
                                                                None,None,None,None,None,
                                                                None,None,self._madInstObj, '',
                                                                catalog_text))
                    catalog_text = ''
                if line.find(start_delimiter) == -1:
                    in_catalog = False
                continue
            if in_catalog and not start_found and len(line.split()) == 0:
                continue
            if in_catalog:
                start_found = True
                catalog_text += line + ' ' * (80 - len(line))
                
        # see if last part was a catalog
        if len(catalog_text) > 0 and len(catalog_text.split()) > 0:
            self._privList.append(MadrigalCatalogRecord(kinst,None,None,None,None,
                                                        None,None,None,None,None,
                                                        None,None,None,None,None,
                                                        None,None,self._madInstObj,
                                                        catalog_text))
            catalog_text = ''
            
            
    def _appendHeaderRecs(self, expNotesDataset):
        """_appendHeaderRecs will append 0 or more MadrigalHeaderRecords to self._privList based
        on the contents in h5py dataset expNotesDataset
        """
        start_delimiter = 'Header information from record'
        end_delimiter = 'Catalog information from record'
        in_header = False
        header_text = ''
        start_found = False
        if len(self._kinstList) > 0:
            kinst = self._kinstList[0]
        else:
            kinst = None
        if len(self._kindatList) > 0:
            kindat = self._kindatList[0]
        else:
            kindat = None
        for line in expNotesDataset:
            line = line[0]
            if type(line) in (bytes, numpy.bytes_):
                line = line.decode('utf8')
            if not in_header and line.find(start_delimiter) != -1:
                in_header = True
                continue
            if in_header and (line.find(end_delimiter) != -1 or line.find(start_delimiter) != -1):
                start_found = False
                if len(header_text) > 0:
                    self._privList.append(MadrigalHeaderRecord(kinst,kindat,None,None,None,None,
                                                               None,None,None,None,None,None,
                                                               None,None,None,None,None,None,
                                                               None,self._madInstObj, 
                                                               self._madKindatObj, header_text))
                    header_text = ''
                if line.find(start_delimiter) == -1:
                    in_header = False
                continue
            if in_header and not start_found and len(line.split()) == 0:
                continue
            if in_header:
                header_text += line + ' ' * (80 - len(line))

                
        # see if last part was a header
        if len(header_text) > 0 and len(header_text.split()) > 0:
            self._privList.append(MadrigalHeaderRecord(kinst,kindat,None,None,None,None,
                                                       None,None,None,None,None,None,
                                                       None,None,None,None,None,None,
                                                       None,self._madInstObj, 
                                                       self._madKindatObj, header_text))
            header_text = ''
            
            
    def _getArraySplitParms(self, metadataGroup):
        """_getArraySplitParms appends a list of parameters used to split arrays (if any) from
        metadataGroup["Parameters Used to Split Array Data"].  If no such table or empty, returns
        empty list
        """
        retList2 = []
        try:
            dset = metadataGroup["Parameters Used to Split Array Data"]
            retList2 = [mnem.lower() for mnem in dset['mnemonic']]
        except:
            return(retList2)
        
        # verify ascii
        retList = []
        for mnem in retList2:
            if type(mnem) in (bytes, numpy.bytes_):
                retList.append(mnem.decode("ascii"))
            else:
                retList.append(mnem)
        
        return(retList)
            
            
            
    def writeExperimentNotes(self, metadataGroup, refreshCatHeadTimes):
        """writeExperimentNotes writes the "Experiment Notes" dataset to the h5py group metadataGroup
        if any catalog or header records found.
        
            refreshCatHeadTimes - if True, update start and and times in the catalog and header
                records to represent the times in the data.  If False, use existing times in those records.
        """
        # templates
        cat_template = 'Catalog information from record %i:'
        head_template = 'Header information from record %i:'
        
        if "Experiment Notes" in list(metadataGroup.keys()):
            # already exists
            return
        
        recDict = {} # key = rec number, value = tuple of recarray of lines, 'Catalog' or 'Header' str)
        for i, rec in enumerate(self._privList):
            if rec.getType() == 'catalog':
                if refreshCatHeadTimes:
                    sDT = self.getEarliestDT()
                    eDT = self.getLatestDT()
                    rec.setTimeLists(sDT.year, sDT.month, sDT.day,
                                     sDT.hour, sDT.minute, sDT.second, int(sDT.microsecond/10000),
                                     eDT.year, eDT.month, eDT.day,
                                     eDT.hour, eDT.minute, eDT.second, int(eDT.microsecond/10000))
                recarray = rec.getLines()
                recDict[i] = (recarray, 'Catalog')
            elif rec.getType() == 'header':
                if refreshCatHeadTimes:
                    sDT = self.getEarliestDT()
                    eDT = self.getLatestDT()
                    rec.setTimeLists(sDT.year, sDT.month, sDT.day,
                                     sDT.hour, sDT.minute, sDT.second, int(sDT.microsecond/10000),
                                     eDT.year, eDT.month, eDT.day,
                                     eDT.hour, eDT.minute, eDT.second, int(eDT.microsecond/10000))
                recarray = rec.getLines()
                recDict[i] = (recarray, 'Header')
                
        keys = list(recDict.keys())
        keys.sort()
        if len(keys) == 0:
            return
        recarray = None
        for key in keys:
            new_recarray = numpy.recarray((2,), dtype=[('File Notes', '|S80')])
            if recDict[key][1] == 'Catalog':
                topStr = cat_template % (key)
            else:
                topStr = head_template % (key)
            new_recarray[0]['File Notes'] = topStr + ' ' * (80 - len(topStr))
            new_recarray[1]['File Notes'] = ' ' * 80
            if recarray is None:
                recarray = new_recarray
            else:
                recarray = numpy.concatenate((recarray, new_recarray))
            recarray = numpy.concatenate((recarray, recDict[key][0]))
            
        metadataGroup.create_dataset('Experiment Notes', data=recarray)
        
        
    def _getKinstList(self, recarr):
        """_getKinstList returns an array of instrument code ints by parsing a numpy recarray
        with columns name and value.  If name is "instrument code(s)", then parse comma separated
        kinst int values in values column. Returns empty list if not found
        """
    
        retList = []
        for i in range(len(recarr)):
            try:
                if int(recarr[i]['name'].decode('utf8').find('instrument code(s)')) != -1:
                    retList = [int(float(kinst)) for kinst in recarr[i]['value'].decode('utf8').split(',')]
                    break
            except AttributeError:
                # not binary
                if int(recarr[i]['name'].find('instrument code(s)')) != -1:
                    retList = [int(float(kinst)) for kinst in recarr[i]['value'].split(',')]
                    break
        return(retList)

    
    def _getKindatList(self, recarr):
        """_getKindatList returns an array of kind of data code ints by parsing a numpy recarray
        with columns name and value.  If name is "kindat code(s)", then parse comma separated
        kindat int values in values column. Returns empty list if not found
        """
        retList = []
        for i in range(len(recarr)):
            try:
                if recarr[i]['name'].decode('utf8').find('kindat code(s)') != -1:
                    retList = [int(float(kindat)) for kindat in recarr[i]['value'].decode('utf8').split(',')]
                    break
            except AttributeError:
                # not binary
                if recarr[i]['name'].find('kindat code(s)') != -1:
                    retList = [int(float(kindat)) for kindat in recarr[i]['value'].split(',')]
                    break
        return(retList)
        
        
    
    def _printSummary(self, f, filterList):
        """_printSummary prints an overview of the original filename and filters used if any
        to open file f (may be stdout)
        
        Inputs:
            f - open file to write to
            
            filterList - a list of madrigal.derivation.MadrigalFilter objects to be described in the 
                summary.  Default is None, in which case not described in summary.  Ignored if summary
                is not 'summary'
        """
        if self._fullFilename is not None:
            f.write('Data derived from file %s:\n' % (self._fullFilename))
            
        if filterList is None:
            return
        
        if len(filterList) == 0:
            return
        
        f.write('Filters used:\n')
        for i in range(len(filterList)):
            f.write('Filter %i:\n' % (i+1))
            f.write('%s\n' % (str(filterList[i])))
        
            
    
    def _getGroupName(self, indValues):
        """_getGroupName returns the name of a array group when split
        
        Input:
            indValues - a list of values, one for each array splitting parameter
        """
        groupName = 'Array with '
        for i, parm in enumerate(self._arraySplitParms):
            if type(parm) in (numpy.bytes_, bytes):
                parmString = parm.decode('utf8')
            else:
                parmString = parm
            groupName += '%s=%s ' % (parmString, str(indValues[i]))
            if i < len(indValues)-1:
                groupName += 'and '
        return(groupName)
        
        

    """ the following methods are added to allow this class to emulate a list."""

    def __len__(self):
        return len(self._privList)
        
    def __getitem__(self, key):
        return self._privList[key]

    def __setitem__(self, key, value):
        # check that value in (MadrigalCatalogRecord, MadrigalHeaderRecord, MadrigalDataRecord)
        if not isinstance(value, MadrigalCatalogRecord) and \
           not isinstance(value, MadrigalHeaderRecord) and \
           not isinstance(value, MadrigalDataRecord):
            # check that its not an empty list (used to delete records)
            okay = False
            if type(value) == list:
                if len(value) == 0:
                    okay = True
            if not okay:
                raise ValueError('In MadrigalCedarFile, can only add MadrigalCatalogRecord, MadrigalHeaderRecord, or MadrigalDataRecord')
        self._privList[key] = value

    def __getslice__(self, i, j):
        return self._privList[i:j]

    def __setslice__(self,i,j,seq):
        # check every item in seq
        for item in seq:
            if not isinstance(value, MadrigalCatalogRecord) and \
               not isinstance(value, MadrigalHeaderRecord) and \
               not isinstance(value, MadrigalDataRecord):
                raise ValueError('In MadrigalCedarFile, can only add MadrigalCatalogRecord, MadrigalHeaderRecord, or MadrigalDataRecord')
        self._privList[max(0, i):max(0, j):] = seq

    def __delslice__(self, i, j):
        del self._privList[max(0, i):max(0, j):]
            
            

    def __delitem__(self, key):
        del self._privList[key]

    def __iter__(self):
        return iter(self._privList)

    def __contains__(self, other):
        for item in self._privList:
            if item == other:
                return 1
        # not found
        return 0

    def __str__(self):
        retStr = ''
        for item in self._privList:
            retStr += '%s\n' % (str(item))
        return retStr
            

    def append(self, item):
        # check that value in (MadrigalCatalogRecord, MadrigalHeaderRecord, MadrigalDataRecord)
        if not isinstance(item, MadrigalCatalogRecord) and \
           not isinstance(item, MadrigalHeaderRecord) and \
           not isinstance(item, MadrigalDataRecord):
            raise ValueError('In MadrigalCedarFile, can only add MadrigalCatalogRecord, MadrigalHeaderRecord, or MadrigalDataRecord')
        if isinstance(item, MadrigalDataRecord):
            if self._tableDType != None:
                if item.getDType() != self._tableDType:
                    raise ValueError('Varying dtypes found: %s versus %s' % (str(item.getDType()), str(self._tableDType)))
            else:
                self.setDType(item.getDType())
                
            if self._recDset is not None:
                if item.getRecordset() != self._recDset:
                    raise ValueError('Varying recordsets found: %s versus %s' % (str(item.getRecordset()), str(self._recDset)))
            else:
                self._recDset = item.getRecordset()
                
            if self._oneDList is None:
                # set all internal data structures set by data records only if not yet set
                self._oneDList = item.get1DParms()
                self._twoDList = item.get2DParms()
                self._ind2DList = item.getInd2DParms()
                # set self._num2DSplit
                twoDSet = set([o.mnemonic for o in self._twoDList])
                arraySplitSet = set(self._arraySplitParms)
                self._num2DSplit = len(twoDSet.intersection(arraySplitSet))
                
            if self._earliestDT is None:
                self._earliestDT = item.getStartDatetime()
                self._latestDT = item.getEndDatetime()
            else:
                if item.getStartDatetime() < self._earliestDT:
                    self._earliestDT = item.getStartDatetime()
                if item.getEndDatetime() > self._latestDT:
                    self._latestDT = item.getEndDatetime()
            if item.getKinst() not in self._kinstList:
                self._kinstList.append(item.getKinst())
            if item.getKindat() not in self._kindatList:
                self._kindatList.append(item.getKindat())
            item.setRecno(self._totalDataRecords)
            self._totalDataRecords += 1
            # update self._recIndexList
            if len(self._recIndexList) > 0:
                lastIndex = self._recIndexList[-1][1]
            else:
                lastIndex = 0
            self._recIndexList.append((lastIndex, lastIndex + len(item.getDataset())))
            if len(self._ind2DList) > 0 and not self._skipArray:
                dataset = item.getDataset()
                rowsToCheck = dataset
                    
                for i, thisRow in enumerate(rowsToCheck):

                    # update self._arrDict
                    if not self._arraySplitParms == []:
                        
                        arraySplitParms = []
                        for parm in self._arraySplitParms:
                            if type(parm) in (numpy.bytes_, bytes):
                                arraySplitParms.append(parm.decode('utf8'))
                            else:
                                arraySplitParms.append(parm)
                        key = tuple([thisRow[parm] for parm in arraySplitParms])

                        # array splitting parameters can never be nan
                        for this_value in key:
                            if not this_value.dtype.type is numpy.bytes_:
                                if numpy.isnan(this_value):
                                    raise ValueError('parm %s is an array splitting parameter, so its illegal to have a nan value for it anywhere in the file' % (str(parm)))
                    else:
                        key = '' # no splitting
                    if key not in list(self._arrDict.keys()):
                        self._arrDict[key] = {}
                        
                    # first add ut1_unix if needed 
                    if 'ut1_unix' in self._arrDict[key]:
                        if thisRow['ut1_unix'] not in self._arrDict[key]['ut1_unix']:
                            self._arrDict[key]['ut1_unix'] = self._arrDict[key]['ut1_unix'].union([thisRow['ut1_unix']])
                    else:
                        self._arrDict[key]['ut1_unix'] = set([thisRow['ut1_unix']])
                    
                    # now deal with all ind parms
                    for parm in self._ind2DList:
                        mnem = parm.mnemonic
                        if mnem in self._arraySplitParms:
                            # no need to create separate dimension since already split out
                            continue
                        
                        if mnem in self._arrDict[key]:
                            if thisRow[mnem] not in self._arrDict[key][mnem]:
                                self._arrDict[key][mnem] = self._arrDict[key][mnem].union([thisRow[mnem]])
                        else:
                            self._arrDict[key][mnem] = set([thisRow[mnem]])
                            
                        # enforce nan rule for ind2DList
                        thisList = list(self._arrDict[key][mnem])
                        if len(thisList) > 0:
                            skip = False
                            if type(thisList[0]) != bytes:
                                skip = True
                            if type(thisList[0]) == numpy.ndarray:
                                if thisList[0].dtype.type is numpy.bytes_:
                                    skip = True
                            if not skip:
                                if numpy.any(numpy.isnan(thisList)):
                                    raise ValueError('Cannot have nan in ind parm %s: %s' % (mnem, str(self._arrDict[key][mnem])))
            
        self._privList.append(item)
        

    def count(self, other):
        return self._privList.count(other)

    def index(self, other):
        return self._privList.index(other)

    def insert(self, i, x):
       self._privList.insert(i, x)

    def pop(self, i):
        return self._privList.pop(i)
        
    def remove(self, x):
        self._privList.remove(x)

    def reverse(self):
        self._privList.reverse()
        
    def sort(self):
        self._privList.sort(key=MadrigalDataRecord.cmpDataRec)
        # reset recno values
        recno = 0
        for rec in self._privList:
            if rec.getType() == 'data':
                rec.set1D('recno', recno)
                recno += 1
        
        
    def __del__(self):
        if not self._closed and self._createFlag and self._format == 'hdf5':
            print(('Warning - created file %s being closed by __del__. Best practice is to call close() directly, to avoid this warning' % (str(self._fullFilename))))
            self.close()


class MadrigalDataRecord:
    """MadrigalDataRecord holds all the information in a Cedar data record."""

    # cedar special values
    missing  = numpy.nan
    assumed  = -1.0
    knownbad = -2.0
    missing_int = numpy.iinfo(numpy.int64).min
    assumed_int = -1
    knownbad_int = -2
    
    # standard parms
    _stdParms = ['year', 'month', 'day', 'hour', 'min', 'sec',
                 'recno', 'kindat', 'kinst', 'ut1_unix', 'ut2_unix']
    
    def __init__(self,kinst=None,
                 kindat=None,
                 sYear=None,sMonth=None,sDay=None,sHour=None,sMin=None,sSec=None,sCentisec=None,
                 eYear=None,eMonth=None,eDay=None,eHour=None,eMin=None,eSec=None,eCentisec=None,
                 oneDList=None,
                 twoDList=None,
                 nrow=None,
                 madInstObj=None,
                 madParmObj=None, 
                 ind2DList=None,
                 dataset=None, recordSet=None, verbose=True,
                 parmObjList=None,
                 madDB=None):
        """__init__ creates a MadrigalDataRecord with all missing data.
        
        Note: all inputs have default values because there are two ways to populate this structure:
        1) with all inputs from kinst to nrow when new data is being created, or 
        2) with numpy arrays dataset and recordSet from existing Hdf5 file.

        Inputs:

            kinst - the kind of instrument code.  A warning will be raised if not in instTab.txt.
                Default is None, in which case recno, dataset, and recordSet must be given.

            kindat - kind of data code. Must be a non-negative integer.
                Default is None, in which case recno, dataset, and recordSet must be given.

            sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec - record start time. sCentisec must be 0-99
                Default is None, in which case recno, dataset, and recordSet must be given.

            eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec - record end time. eCentisec must be 0-99
                Default is None, in which case recno, dataset, and recordSet must be given.

            oneDList - list of one-dimensional parameters in record. Parameters can be defined as codes
                       (integers) or case-insensitive mnemonic strings (eg, "Gdalt"), or CedarParameter objects.
                       Default is None, in which case recno, dataset, and recordSet must be given.

            twoDList - list of two-dimensional parameters in record. Parameters can be defined as codes
                       (integers) or case-insensitive mnemonic strings (eg, "Gdalt"), or CedarParameter objects.
                       Default is None, in which case recno, dataset, and recordSet must be given.

            nrow - number of rows of 2D data to create. Until set, all values default to missing.
                Default is None, in which case recno, dataset, and recordSet must be given.

            madInstObj - a madrigal.metadata.MadrigalInstrument object.  If None, one will be created.
                              Used to verify kinst.

            madParmObj - a madrigal.data.MadrigalParameter object.  If None, one will be created.
                              Used to verify convert parameters to codes.
                              
            ind2DList -  list of indepedent spatial two-dimensional parameters in record. 
                       Parameters can be defined as codes. Each must also be listed in twoDList.
                       (integers) or case-insensitive mnemonic strings (eg, "Gdalt"), or CedarParameter objects.
                       Default is None, in which case dataset, and recordSet must be given.
                
            dataset - an h5py dataset, as found in the Hdf5 group "Data", dataset "Table Layout".
                Set to None if this is a new record.
                
            recordSet - an h5py dataset, as found in the Hdf5 group "Metadata", dataset "_record_layout".
                Set to None if this is a new record.
                
            verbose - if True (the default), print all warnings.  If False, surpress warnings
            
            parmObjList - a list or tuple of three lists: self._oneDList, self._twoDList, and
                self._ind2DList described below.  Used only to speed performance.  Default is
                None, in which case new copies are created.
                
            madDB - madrigal.metadata.MadrigalDB object. If None, one will be created.

        Outputs: None

        Returns: None
        
        Affects:
            Creates attributes:
                self._madInstObj - madrigal.metadata.MadrigalInstrument object
                self._madParmObj - madrigal.data.MadrigalParameters object
                self._dataset - h5py dataset in from of Table Layout numpy recarray
                self._recordSet - h5py dataset in form of _record_layout numpy recarray
                self._verbose - bool indicating verbose or not
                self._oneDList - a list of 1D CedarParameter objects in this MadrigalDataRecord
                self._twoDList - a list of 2D CedarParameter objects in this MadrigalDataRecord
                self._ind2DList - a list of independent spatial parameters in self._twoDList
        """
        if madDB is None:
            self._madDB = madrigal.metadata.MadrigalDB()
        else:
            self._madDB = madDB
        # create any needed Madrigal objects, if not passed in
        if madInstObj is None:
            self._madInstObj = madrigal.metadata.MadrigalInstrument(self._madDB)
        else:
            self._madInstObj = madInstObj

        if madParmObj is None:
            self._madParmObj = madrigal.data.MadrigalParameters(self._madDB)
        else:
            self._madParmObj = madParmObj


        if twoDList is None:
            twoDList = []
            
        if ind2DList is None:
            ind2DList = []
            
        if dataset is None or recordSet is None:
            if ind2DList is None:
                # get it from cachedFiles.ini
                extraParms, ind2DList, splitParms = self._madDB.getKinstKindatConfig(kinst, kindat)
            # verify there are independent spatial parms if there are 2D parms
            if not len(twoDList) == 0 and len(ind2DList) == 0:
                raise ValueError('Cannot have 2D parms without an independent spatial parm set') 
            self._createArraysFromArgs(kinst,kindat,sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec,
                                       eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec,
                                       oneDList,twoDList,nrow,ind2DList)
        else:
            # verify there are independent spatial parms if there are 2D parms
            if not len(twoDList) == 0 and len(ind2DList) == 0:
                raise ValueError('Cannot have 2D parms without an independent spatial parm set')
            self._dataset = dataset
            self._recordSet = recordSet
            
        if parmObjList is not None:
            self._oneDList = copy.deepcopy(parmObjList[0])
            self._twoDList = copy.deepcopy(parmObjList[1])
            self._ind2DList = copy.deepcopy(parmObjList[2])
        else:
            # populate self._oneDList, self._twoDList, and self._ind2DList
            self._oneDList = []
            self._twoDList = []
            self._ind2DList = []
            for parm in self._recordSet.dtype.names[len(self._stdParms):]:
                if self.parmIsInt(parm):
                    isInt = True
                else:
                    isInt = False
                newCedarParm = CedarParameter(self._madParmObj.getParmCodeFromMnemonic(parm),
                                              parm, self._madParmObj.getParmDescription(parm),
                                              isInt)
                if self._recordSet[parm][0] == 1:
                    self._oneDList.append(newCedarParm)
                if self._recordSet[parm][0] in (2,3):
                    self._twoDList.append(newCedarParm)
                if self._recordSet[parm][0] == 3:
                    self._ind2DList.append(newCedarParm)
        
            
        self._verbose = bool(verbose)
        
    
    
    def getType(self):
        """ returns the type 'data'"""
        return 'data'
    
    
    def getDType(self):
        """getDType returns the dtype of the table array with this data
        """
        return(self._dataset.dtype)
    
    
    def getRecDType(self):
        """getRecDType returns the dtype of _record_array
        """
        return(self._recordSet.dtype)
    
    
    def getDataset(self):
        """getDataset returns the dataset table
        """
        return(self._dataset)
    
    def getRecordset(self):
        """getRecordset returns the recordSet table
        """
        return(self._recordSet)
    
    
    def parmIsInt(self, parm):
        """parmIsInt returns True if this parm (mnemonic) is integer type, False if float or string
        
        Raises ValueError if parm not in record
        """
        try:
            typeStr = str(self._dataset.dtype[parm.lower()].kind)
        except KeyError:
            raise ValueError('Parm <%s> not found in file' % (str(parm)))
        if typeStr.find('i') != -1:
            return(True)
        else:
            return(False)
        
        
    def parmIsString(self, parm):
        """parmIsString returns True if this parm (mnemonic) is String type, False if float or int
        
        Raises ValueError is parm not in record
        """
        try:
            typeStr = str(self._dataset.dtype[parm.lower()].kind)
        except KeyError:
            raise ValueError('Parm <%s> not found in file' % (str(parm)))
        if typeStr.find('S') != -1:
            return(True)
        else:
            return(False)
        
        
    def getStrLen(self, parm):
        """getStrLen returns True if this parm (mnemonic) is integer type, False if float or string
        
        Raises ValueError is parm not in record, or is not String
        """
        if not self.parmIsString(parm):
            raise ValueError('Parm <%s> not string type' % (str(parm)))
        return(self._dataset.dtype[parm.lower()].itemsize)
    


    def add1D(self, oneDParm):
        """add1D adds a new one-dim parameter to a MadrigalDataRecord

        Input: oneDParm - Parameter can be defined as codes (integer) or case-insensitive
               mnemonic string (eg, "Gdalt")

        Affects: 1) adds new column to self._dataset with all values Nan, and 2) adds 
        value to end of self._recordSet with value = 1 since 1D parm
        
        If these addition makes self._dataset.dtype differ from that in MadrigalCedarFile, appending this
        MadrigalDataRecord to MadrigalCedarFile will raise an IOError. Also raises error if parm already exists.
        """
        self.addParm(oneDParm, 1)



    def add2D(self, twoDParm):
        """add2D adds a new two-dim parameter to a MadrigalDataRecord

        Input: twoDParm - Parameter can be defined as codes (integer) or case-insensitive
               mnemonic string (eg, "Gdalt")

        Affects: 1) adds new column to self._dataset with all values Nan, and 2) adds 
        value to end of self._recordSet with value = 2 since 2D parm
        
        If these addition makes self._dataset.dtype differ from that in MadrigalCedarFile, appending this
        MadrigalDataRecord to MadrigalCedarFile will raise an IOError. Also raises error if parm already exists.
        """
        self.addParm(twoDParm, 2)
        
        

    def addParm(self, newParm, dim):
        """addParm adds a new one or two-dim parameter to a MadrigalDataRecord

        Input: newParm - Parameter can be defined as codes (integer) or case-insensitive
               mnemonic string (eg, "Gdalt")
               
               dim - either 1 for scalar, or 2 for vector parm

        Affects: 1) adds new column to self._dataset with all values Nan, and 2) adds 
        value to end of self._recordSet with value = dim
        
        If these addition makes self._dataset.dtype differ from that in MadrigalCedarFile, appending this
        MadrigalDataRecord to MadrigalCedarFile will raise an IOError. Also raises error if parm already exists.
        """
        if dim not in (1,2):
            raise ValueError('dim must be 1 or 2, not %s' % (str(dim)))
        
        # see if its an integer
        try:
            code = int(newParm)
            isInt = True
        except:
            isInt = False

        if isInt:
            # try to look up mnemonic
            mnem = self._madParmObj.getParmMnemonic(int(newParm)).lower()
            if mnem == str(newParm):
                raise IOError('Cannot use unknown parm %i' % (int(newParm)))
        else:
            # this must succeed or an exception raised
            try:
                code = self._madParmObj.getParmCodeFromMnemonic(newParm.lower())
            except ValueError:
                raise IOError('Mnem %s not found' % (newParm))
            mnem = newParm.lower()

        # issue warning if an unneeded time parameter being added
        if self._verbose and abs(code) < timeParms:
            sys.stderr.write('WARNING: Parameter %s is a time parameter that potentially conflicts with prolog times\n' % (parm[1]))

        # figure out dtype
        format = self._madParmObj.getParmFormat(mnem)
        if format[-1] == 'i':
            dtype = numpy.int64
        else:
            dtype = numpy.float64
            
        data = numpy.zeros((len(self._dataset),), dtype)
        data[:] = numpy.nan
        self._dataset = numpy.lib.recfunctions.append_fields(self._dataset, mnem, data)
        data = numpy.array([dim], numpy.int64)
        self._recordSet = numpy.lib.recfunctions.append_fields(self._recordSet, mnem, data, usemask=False)

        newCedarParm = CedarParameter(self._madParmObj.getParmCodeFromMnemonic(mnem),
                                      mnem, self._madParmObj.getParmDescription(mnem),
                                      isInt)
        
        if dim == 1:
            self._oneDList.append(newCedarParm)
        else:
            self._twoDList.append(newCedarParm)


    def set1D(self, parm, valueIn):
        """set1D sets a 1D value for a given 1D parameter

        Inputs:

            parm - can be defined as code (integer) or case-insensitive mnemonic string (eg, "Gdalt")


            valueIn - double (or string convertable to double) value to set 1D parameter to.  To set special Cedar values, the global values
                    missing, assumed, or knownbad may be used, or the strings "missing", "assumed", or "knownbad"
                    May also be int or string if that type

        Outputs: None
        """
        parm = self._madParmObj.getParmMnemonic(parm).lower()
        # avoid numpy / python disagreement when comparing strings/arrays
        try:
            if valueIn.dtype.type == numpy.str_:
                value = str(valueIn)
            else:
                value = valueIn[0]
        except:
            value = valueIn
            
        if value == 'missing':
            if self.parmIsInt(parm):
                value = self.missing_int
            elif self.parmIsString(parm):
                value = ' ' * self.getStrLen(parm)
            else:
                value = self.missing
            
        if self._madParmObj.isError(parm):
            if value == 'assumed':
                if self.parmIsInt(parm):
                    value = self.assumed_int
                else:
                    value = self.assumed
            elif value == 'knownbad':
                if self.parmIsInt(parm):
                    value = self.knownbad_int
                else:
                    value = self.knownbad
        elif value in ('assumed', 'knownbad'):
            raise ValueError('It is illegal to set the non-error parm %s to %s' % (parm, value))

        # make sure this is a one-d parm
        try:
            dim = self._recordSet[parm]
        except ValueError:
            raise ValueError('parm %s does not exist' % (str(parm)))
        if dim != 1:
            raise ValueError('parm %s is 2D, not 1D' % (str(parm)))
        
        # set it
        self._dataset[parm] = value
        


    def set2D(self, parm, row, valueIn):
        """set2D sets a 2D value for a given 2D parameter and row

        Inputs:

            parm - can be defined as code (integer) or case-insensitive mnemonic string (eg, "Gdalt")

            row - row number to set data.  Starts at 0.

            valueIn - double (or string convertable to double) value to set 2D parameter to. To set special Cedar values, the global values
                    missing, assumed, or knownbad may be used, or the strings "missing", "assumed", or "knownbad"
                    May also be int or string if that type

        Outputs: None

        """
        if row >= len(self._dataset) or row < 0:
            raise ValueError('Illegal value of row %i with nrow = %i' % (row,len(self._dataset)))
        
        parm = self._madParmObj.getParmMnemonic(parm).lower()
        isString = self._madParmObj.isString(parm)
        
        # avoid numpy / python disagreement when comparing strings
        try:
            if valueIn.dtype.type == numpy.str_:
                value = str(valueIn)
            else:
                value = valueIn[0]
        except:
            value = valueIn
        
        if value == 'missing':
            if self.parmIsInt(parm):
                value = self.missing_int
            elif self.parmIsString(parm):
                value = ' ' * self.getStrLen(parm)
            else:
                value = self.missing
            
        if self._madParmObj.isError(parm):
            if value == 'assumed':
                if self.parmIsInt(parm):
                    value = self.assumed_int
                else:
                    value = self.assumed
            elif value == 'knownbad':
                if self.parmIsInt(parm):
                    value = self.knownbad_int
                else:
                    value = self.knownbad
        elif value in ('assumed', 'knownbad'):
            raise ValueError('It is illegal to set the non-error parm %s to %s' % (parm, value))

        # make sure this is a two-d parm
        try:
            dim = self._recordSet[parm]
        except ValueError:
            raise ValueError('parm %s does not exist' % (str(parm)))
        if dim not in (2, 3):
            raise ValueError('parm %s is 1D, not 2D' % (str(parm)))
        
        # if its ind parm, make sure its not nan
        if parm in self._ind2DList:
            if not isString:
                if numpy.isnan(value):
                    raise ValueError('Cannot set ind parm %s to nan at row %i' % (parm, row))
        
        
        # set it
        self._dataset[parm][row] = value
        
        
    def set2DParmValues(self, parm, values):
        """set2DParmValues sets all 2D value in all rows for a given 2D parameter

        Inputs:

            parm - can be defined as code (integer) or case-insensitive mnemonic string (eg, "Gdalt")

            value - list, tuple, or numpy array of int64 or float64 type.  Must match len of nrows.  User is responsible
                for having set all special values to missing, assumed and knownbad as defined at top
                of this class for either ints or floats

        Outputs: None

        """
        # make sure this is a two-d parm
        parm = self._madParmObj.getParmMnemonic(parm).lower()
        isString = self._madParmObj.isString(parm)
        try:
            dim = self._recordSet[parm]
        except ValueError:
            raise ValueError('parm %s does not exist' % (str(parm)))
        if dim not in (2, 3):
            raise ValueError('parm %s is 1D, not 2D' % (str(parm)))
        
        if parm in self._ind2DList:
            if not isString:
                if numpy.any(numpy.isnan(values)):
                    raise ValueError('Cannot set any ind parm %s value to nan: %s' % (parm, str(values)))
        
        # set it
        self._dataset[parm] = values



    def get1D(self, parm):
        """get1D returns the 1D value for a given 1D parameter

        Inputs:

            parm - can be defined as code (integer) or case-insensitive mnemonic string (eg, "Gdalt")

        Outputs: value
        """    
        # make sure this is a one-d parm
        parm = self._madParmObj.getParmMnemonic(parm).lower()
        isString = self._madParmObj.isString(parm)
        try:
            dim = self._recordSet[parm]
        except ValueError:
            raise ValueError('parm %s does not exist' % (str(parm)))
        if dim != 1:
            raise ValueError('parm %s is 2D, not 1D' % (str(parm)))
                
        value = self._dataset[parm][0]

        # check for special values
        if not isString:
            if numpy.isnan(value):
                return('missing')

        # if its an error parameter, allow assumed or knownbad
        if self._madParmObj.isError(parm):
            if int(value) == self.assumed_int:
                return('assumed')
            if int(value) == self.knownbad_int:
                return('knownbad')

        return value


    def get2D(self, parm, row):
        """get2D returns the 2D value for a given 2D parameter

        Inputs:

            parm - can be defined as code (integer) or case-insensitive mnemonic string (eg, "Gdalt")

            row - row number to get data.  Starts at 0.

        Outputs: double value, or the strings "missing", "assumed", or "knownbad"
        """    
        if row >= len(self._dataset) or row < 0:
            raise ValueError('Illegal value of row %i with nrow = %i' % (row,len(self._dataset)))
        
        # make sure this is a two-d parm
        parm = self._madParmObj.getParmMnemonic(parm).lower()
        isString = self._madParmObj.isString(parm)
        try:
            dim = self._recordSet[parm]
        except ValueError:
            raise ValueError('parm %s does not exist' % (str(parm)))
        if dim not in (2,3):
            raise ValueError('parm %s is 1D, not 2D' % (str(parm)))
                
        value = self._dataset[parm][row]

        # check for special values
        if not isString:
            if numpy.isnan(value):
                return('missing')

        # if its an error parameter, allow assumed or knownbad
        if self._madParmObj.isError(parm):
            if int(value) == self.assumed_int:
                return('assumed')
            if int(value) == self.knownbad_int:
                return('knownbad')

        return value
    
    
    def getRow(self, row):
        """getRow returns the row of data in order defined in self._dataset.dtype
        
        Input: row number
        
        IndexError raised if not a valid row index
        """
        return(self._dataset[row])
    
    
    def setRow(self, row, values):
        """setRow sets an entire row of data at once
        
        Inputs:
        
            row - row number to set
            
            values - a tuple of values in the right format to match self._dataset.dtype
        """
        self._dataset[row] = values


    def delete1D(self, parm):
        """delete1D removes the given 1D parameter from the record

        Inputs:

            parm - can be defined as code (integer) or case-insensitive mnemonic string (eg, "Gdalt")

        Outputs: None

        Raise exception if 1D parm does not exist. If this deletion makes self._dataset.dtype differ from that in 
        MadrigalCedarFile, appending this MadrigalDataRecord to MadrigalCedarFile will raise an IOError. 
        """
        # make sure this is a one-d parm
        parm = self._madParmObj.getParmMnemonic(parm).lower()
        try:
            dim = self._recordSet[parm]
        except ValueError:
            raise ValueError('parm %s does not exist' % (str(parm)))
        if dim != 1:
            raise ValueError('parm %s is 2D, not 1D' % (str(parm)))
        
        self._dataset = numpy.lib.recfunctions.drop_fields(self._dataset, parm)
        self._recordSet = numpy.lib.recfunctions.drop_fields(self._recordSet, parm)
        
        # find index to delete from self._oneDList
        index = None
        for i, parmObj in enumerate(self._oneDList):
            if parmObj.mnemonic == parm:
                index = i
                break
        if index is None:
            raise ValueError('Did not find parm %s in self._oneDList' % (str(parm)))
        del self._oneDList[index]
        

    def delete2DParm(self, parm):
        """delete2DParm removes the given 2D parameter from every row in the record

        Inputs:

            parm - can be defined as code (integer) or case-insensitive mnemonic string (eg, "Gdalt")

        Outputs: None

        Raise exception if 2D parm does not exist. If this deletion makes self._dataset.dtype differ from that in 
        MadrigalCedarFile, appending this MadrigalDataRecord to MadrigalCedarFile will raise an IOError. 
        """
        
        # make sure this is a two-d parm
        parm = self._madParmObj.getParmMnemonic(parm).lower()
        try:
            dim = self._recordSet[parm]
        except ValueError:
            raise ValueError('parm %s does not exist' % (str(parm)))
        if dim not in (2,3):
            raise ValueError('parm %s is 1D, not 2D' % (str(parm)))
        
        self._dataset = numpy.lib.recfunctions.drop_fields(self._dataset, parm)
        self._recordSet = numpy.lib.recfunctions.drop_fields(self._recordSet, parm)

        # find index to delete from self._twoDList
        index = None
        for i, parmObj in enumerate(self._twoDList):
            if parmObj.mnemonic == parm:
                index = i
                break
        if index is None:
            raise ValueError('Did not find parm %s in self._twoDList' % (str(parm)))
        del self._twoDList[index]
        
        

    def delete2DRows(self, rows):
        """delete2DRows removes the given 2D row or rows in the record (first is row 0)

        Inputs:

            row number (integer) or list of row numbers to delete (first is row 0)

        Outputs: None

        Raise exception if row does not exist
        """
        # make sure row is a list
        if type(rows) in (int, int):
            rows = [rows]
            
        keepIndices = []
        count = 0 # make sure all rows actually exist
        for i in range(self.getNrow()):
            if i not in rows:
                keepIndices.append(i)
            else:
                count += 1
        if count != len(rows):
            raise ValueError('Some row in %s out of range, total number of rows is %i' % (str(rows), self.getNrow()))
        
        self._dataset = self._dataset[keepIndices]
        
        

    def getKinst(self):
        """getKinst returns the kind of instrument code (int) for a given data record.

        Inputs: None

        Outputs: the kind of instrument code (int) for a given data record.
        """
        return(self._dataset['kinst'][0])


    def setKinst(self, newKinst):
        """setKinst sets the kind of instrument code (int) for a given data record.

        Inputs: newKinst - new instrument code (integer)

        Outputs: None

        Affects: sets self._dataset['kinst']
        """
        newKinst = int(newKinst)
        if newKinst < 0:
            raise ValueError('Kinst must not be less than 0, not %i' % (newKinst))
        # verify  and set kinst
        instList = self._madInstObj.getInstrumentList()
        found = False
        for inst in instList:
            if inst[2] == newKinst:
                self._instrumentName = inst[0]
                found = True
                break
        if found == False:
            self._instrumentName = 'Unknown instrument'
            sys.stderr.write('Warning: kinst %i not found in instTab.txt\n' % (newKinst))

        self._dataset['kinst'] = newKinst


    def getKindat(self):
        """getKindat returns the kind of data code (int) for a given data record.

        Inputs: None

        Outputs: the kind of data code (int) for a given data record.
        """
        return(int(self._dataset['kindat'][0]))


    def setKindat(self, newKindat):
        """setKindat sets the kind of data code (int) for a given data record.

        Inputs: newKindat (integer)

        Outputs: None

        Affects: sets self._dataset['kindat']
        """
        if int(newKindat) < 0:
            raise ValueError('kindat cannot be negative: %i' % (int(newKindat)))
        self._dataset['kindat'] = int(newKindat)
        
        
    def getRecno(self):
        """getRecno returns the recno (int) for a given data record.

        Inputs: None

        Outputs: the recno (int) for a given data record. May be 0 if not yet in a file
        """
        return(self._dataset['kindat'][0])


    def setRecno(self, newRecno):
        """setRecno sets the recno (int) for a given data record.

        Inputs: newRecno (integer)

        Outputs: None

        Affects: sets self._dataset['recno']
        """
        if int(newRecno) < 0:
            raise ValueError('recno cannot be negative: %i' % (int(newRecno)))
        self._dataset['recno'] = int(newRecno)


    def getNrow(self):
        """getNrow returns the number of 2D data rows (int) for a given data record.

        Inputs: None

        Outputs: the number of 2D data rows.
        """
        return(len(self._dataset))


    def getStartTimeList(self):
        """getStartTimeList returns a tuple containing sYear, sMonth, sDay, sHour, sMin, sSec, and sCentisec

        Inputs: None

        Outputs: a tuple containing sYear, sMonth, sDay, sHour, sMin, sSec, and sCentisec.
        """
        startDT = self.getStartDatetime()
        return((startDT.year, startDT.month, startDT.day, 
                startDT.hour, startDT.minute, startDT.second, int(startDT.microsecond/1.0E4)))
        
        
    def getStartDatetime(self):
        """getStartDatetime returns a start record datetime

        Inputs: None

        Outputs: a datetime.datetime object representing the start time of the record
        """
        return(datetime.datetime.fromtimestamp(self._dataset['ut1_unix'][0], datetime.UTC))


    def setStartTimeList(self, sYear, sMonth, sDay, sHour, sMin, sSec, sCentisec=0):
        """setStartTimeList changes the data record start time

        Inputs: integers sYear, sMonth, sDay, sHour, sMin, sSec. sCentisec defaults to 0

        Outputs: None

        Affects: changes self._dataset fields ut1_unix, year, month, day, hour, min,sec

        Prints warning if new start time after present end time
        """
        # check validity of input time
        sCentisec = int(sCentisec)
        if sCentisec < 0 or sCentisec > 99:
            raise ValueError('Illegal sCentisec %i' % (sCentisec))
        
        try:
            sDT = datetime.datetime(sYear, sMonth, sDay, sHour, sMin, sSec, int(sCentisec*1E4))
        except:
            raise ValueError('Illegal datetime %s' % (str((sYear, sMonth, sDay, sHour, sMin, sSec, sCentisec))))

        if sDT > self.getEndDatetime():
            sys.stderr.write('Warning: New starting time %s after present ending time %s\n' % (str(sDT), 
                                                                                               str(self.getEndDatetime())))
            
        ut1_unix = (sDT - datetime.datetime(1970,1,1)).total_seconds()
        
        self._dataset['ut1_unix'] = ut1_unix
        
        # need to reset average time
        aveDT = sDT + (self.getEndDatetime() - sDT)/2
        self._dataset['year'] = aveDT.year
        self._dataset['month'] = aveDT.month
        self._dataset['day'] = aveDT.day
        self._dataset['hour'] = aveDT.hour
        self._dataset['min'] = aveDT.minute
        self._dataset['sec'] = aveDT.second



    def getEndTimeList(self):
        """getEndTimeList returns a tuple containing eYear, eMonth, eDay, eHour, eMin, eSec, and eCentisec

        Inputs: None

        Outputs: a tuple containing eYear, eMonth, eDay, eHour, eMin, eSec, and eCentisec.
        """
        endDT = self.getEndDatetime()
        return((endDT.year, endDT.month, endDT.day, 
                endDT.hour, endDT.minute, endDT.second, int(endDT.microsecond/1.0E4)))
        
        
    def getEndDatetime(self):
        """getEndDatetime returns a end record datetime

        Inputs: None

        Outputs: a datetime.datetime object representing the end time of the record
        """
        return(datetime.datetime.fromtimestamp(self._dataset['ut2_unix'][0], datetime.UTC))
    
    
    def setEndTimeList(self, eYear, eMonth, eDay, eHour, eMin, eSec, eCentisec=0):
        """setEndTimeList changes the data record end time

        Inputs: integers eYear, eMonth, eDay, eHour, eMin, eSec. eCentisec defaults to 0

        Outputs: None

        Affects: changes self._dataset fields ut2_unix, year, month, day, hour, min,sec

        Prints warning if new start time after present end time
        """
        # check validity of input time
        eCentisec = int(eCentisec)
        if eCentisec < 0 or eCentisec > 99:
            raise ValueError('Illegal eCentisec %i' % (eCentisec))
        
        try:
            eDT = datetime.datetime(eYear, eMonth, eDay, eHour, eMin, eSec, int(eCentisec*1E4))
        except:
            raise ValueError('Illegal datetime %s' % (str((eYear, eMonth, eDay, eHour, eMin, eSec, eCentisec))))

        if eDT < self.getStartDatetime():
            sys.stderr.write('Warning: New ending time %s before present starting time %s\n' % (str(eDT), 
                                                                                                str(self.getStartDatetime())))
            
        ut2_unix = (eDT - datetime.datetime(1970,1,1)).total_seconds()
        
        self._dataset['ut2_unix'] = ut2_unix
        
        # need to reset average time
        aveDT = eDT - (eDT - self.getStartDatetime())/2
        self._dataset['year'] = aveDT.year
        self._dataset['month'] = aveDT.month
        self._dataset['day'] = aveDT.day
        self._dataset['hour'] = aveDT.hour
        self._dataset['min'] = aveDT.minute
        self._dataset['sec'] = aveDT.second


    


    def get1DParms(self):
        """get1DParms returns a list of 1D parameters in the MadrigalDataRecord.

        Inputs: None

        Outputs: a list of 1D CedarParameter objects in the MadrigalDataRecord.
        """
        return(self._oneDList)


    def get2DParms(self):
        """get2DParms returns a list of 2D parameters in the MadrigalDataRecord.

        Inputs: None

        Outputs: a list of 2D CedarParameter objects in the MadrigalDataRecord. Includes
            both independent and dependent parms.
        """
        return(self._twoDList)
    
    
    def getInd2DParms(self):
        """getInd2DParms returns a list of the subset 2D parameters ithat are independent parmeters.

        Inputs: None

        Outputs: a list of independent 2D CedarParameter objects in the MadrigalDataRecord. 
        """
        return(self._ind2DList)
    
    
    def getParmDim(self, parm):
        """getParmDim returns the dimension (1, 2, or 3 for independent spatial parm) of a given parm mnemonic
        
        Raise KeyError if that parameter not found in file
        """
        for obj in self._oneDList:
            if obj.mnemonic.lower() == parm.lower():
                return(1)
        # do ind 2D next since they are in both lists
        for obj in self._ind2DList:
            if obj.mnemonic.lower() == parm.lower():
                return(3)
        for obj in self._twoDList:
            if obj.mnemonic.lower() == parm.lower():
                return(2)
        
        raise KeyError('Parm <%s> not found in data' % (str(parm)))
    

    def getHeaderKodLines(self):
        """getHeaderKodLines creates the lines in the Madrigal header record that start KOD and describe parms

        Inputs: None

        Returns: a string of length 80*num parms.  Each 80 characters contains a description
                 of a single parm accodring to the Cedar Standard
        """
        # create a list of oneDCedar codes for the data record.
        #  Each item has three elements: (code, parameter description, units)
        oneDCedarCodes = []
        for parm in self._oneDList:
            oneDCedarCodes.append((parm.code, self._madParmObj.getSimpleParmDescription(parm.code),
                                   self._madParmObj.getParmUnits(parm.code)))
        
        oneDCedarCodes.sort(key=compareParms)

        # create a list of twoDCedar codes for the data record.
        # Each item has three elements: (code, parameter description, units)
        twoDCedarCodes = []
        for parm in self._twoDList:
            twoDCedarCodes.append((parm.code, self._madParmObj.getSimpleParmDescription(parm.code),
                                   self._madParmObj.getParmUnits(parm.code)))
            
        twoDCedarCodes.sort(key=compareParms)
        

        # write out lines - one D
        retStr = ''
        if len(oneDCedarCodes) > 0:
            retStr += 'C 1D Parameters:' + (80 - len('C 1D Parameters:'))*' '
        for i in range(len(oneDCedarCodes)):
            code = oneDCedarCodes[i][0]
            desc = oneDCedarCodes[i][1]
            units = oneDCedarCodes[i][2]
            line = 'KODS(%i)' % (i)
            line += (10-len(line))*' '
            codeNum = str(code)
            codeNum = (10-len(codeNum))* ' ' + codeNum
            line += codeNum
            if len(desc) > 48:
                desc = ' ' + desc[:48] + ' '
            else:
                desc = ' ' + desc + (49-len(desc))* ' '
            line += desc
            units = units[:10] + (10-len(units[:10]))*' '
            line += units
            retStr += line

        # two D
        if len(twoDCedarCodes) > 0:
            retStr += 'C 2D Parameters:' + (80 - len('C 2D Parameters:'))*' '
        for i in range(len(twoDCedarCodes)):
            code = twoDCedarCodes[i][0]
            desc = twoDCedarCodes[i][1]
            units = twoDCedarCodes[i][2]
            line = 'KODM(%i)' % (i)
            line += (10-len(line))*' '
            codeNum = str(code)
            codeNum = (10-len(codeNum))* ' ' + codeNum
            line += codeNum
            if len(desc) > 48:
                desc = ' ' + desc[:48] + ' '
            else:
                desc = ' ' + desc + (49-len(desc))* ' '
            line += desc
            units = units[:10] + (10-len(units[:10]))*' '
            line += units
            retStr += line

        return(retStr)

                    

    
        
        
    def _createArraysFromArgs(self,kinst,kindat,sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec,
                                       eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec,
                                       oneDList,twoDList,nrow,ind2DList):
        """_createArraysFromArgs creates a table layout array and record array numpy array based in input arguments.
        
        Inputs:

            kinst - the kind of instrument code.  A warning will be raised if not in instTab.txt.
                Default is None, in which case recno, dataset, and recordSet must be given.

            kindat - kind of data code. Must be a non-negative integer.
                Default is None, in which case recno, dataset, and recordSet must be given.

            sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec - record start time. sCentisec must be 0-99
                Default is None, in which case recno, dataset, and recordSet must be given.

            eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec - record end time. eCentisec must be 0-99
                Default is None, in which case recno, dataset, and recordSet must be given.

            oneDList - list of one-dimensional parameters in record. Parameters can be defined as codes
                       (integers) or case-insensitive mnemonic strings (eg, "Gdalt"), or CedarParameter objects.
                       Default is None, in which case recno, dataset, and recordSet must be given.

            twoDList - list of two-dimensional parameters in record. Parameters can be defined as codes
                       (integers) or case-insensitive mnemonic strings (eg, "Gdalt"), or CedarParameter objects.
                       Default is None, in which case recno, dataset, and recordSet must be given.

            nrow - number of rows of 2D data to create. Until set, all values default to missing.
                Default is None, in which case recno, dataset, and recordSet must be given.
                
            ind2DList -  list of indepedent spatial two-dimensional parameters in record. 
                       Parameters can be defined as codes. Each must also be listed in twoDList.
                       (integers) or case-insensitive mnemonic strings (eg, "Gdalt"), or CedarParameter objects.
                       Default is None, in which case dataset, and recordSet must be given.
            
        """
        defaultParms = self._stdParms
        dataDtype = [] # data type for the Table Layout recarray
        recDType = [] # data type for _record_layout recarray
        recDims = [] # dimension of each parameter (1 for 1D, 2 for dependent 2D, 3 for independent 2D)
        parmsAddedSoFar = [] # mnemonics added so far
        
        # the following is simply to ensure that independent 2D parms are also listed in twoDList
        twoDParms = []
        for parm in twoDList:
            if isinstance(parm, CedarParameter):
                parm = parm.mnemonic
            mnem = self._madParmObj.getParmMnemonic(parm)
            if mnem in twoDParms:
                raise ValueError('Duplicate parmeter %s in twoDList' % (mnem))
            twoDParms.append(mnem)
        
        # default parms
        for parm in defaultParms:
            mnem = self._madParmObj.getParmMnemonic(parm)
            if self._madParmObj.isInteger(mnem):
                dataDtype.append((mnem.lower(), int))
            else: # default parms cannot be strings
                dataDtype.append((mnem.lower(), float))
            recDType.append((parm.lower(), int))
            recDims.append(1)
            parmsAddedSoFar.append(mnem)
            
        # one D parms
        for parm in oneDList:
            if isinstance(parm, CedarParameter):
                parm = parm.mnemonic
            mnem = self._madParmObj.getParmMnemonic(parm)
            if mnem in parmsAddedSoFar:
                continue # legal because it may be a default parm
            if self._madParmObj.isInteger(mnem):
                dataDtype.append((mnem.lower(), int))
            elif self._madParmObj.isString(mnem):
                strLen = self._madParmObj.getStringLen(mnem)
                dataDtype.append((mnem.lower(), numpy.bytes_, strLen))
            else: 
                dataDtype.append((mnem.lower(), float))
            recDType.append((parm.lower(), int))
            recDims.append(1)
            parmsAddedSoFar.append(mnem)
            
        for parm in ind2DList:
            if isinstance(parm, CedarParameter):
                parm = parm.mnemonic
            mnem = self._madParmObj.getParmMnemonic(parm)
            if mnem in parmsAddedSoFar:
                raise ValueError('Duplicate parmeter %s' % (mnem))
            if mnem not in twoDParms:
                raise ValueError('Independent 2D parm %s not found in twoDList' % (mnem))
            
            if self._madParmObj.isInteger(mnem):
                dataDtype.append((mnem.lower(), int))
            elif self._madParmObj.isString(mnem):
                strLen = self._madParmObj.getStringLen(mnem)
                dataDtype.append((mnem.lower(), numpy.bytes_, strLen))
            else: 
                dataDtype.append((mnem.lower(), float))
            recDType.append((parm.lower(), int))
            recDims.append(3)
            parmsAddedSoFar.append(mnem)
            
        for parm in twoDList:
            if isinstance(parm, CedarParameter):
                parm = parm.mnemonic
            mnem = self._madParmObj.getParmMnemonic(parm)
            if mnem in parmsAddedSoFar:
                continue # legal because may be independent parm
            if self._madParmObj.isInteger(mnem):
                dataDtype.append((mnem.lower(), int))
            elif self._madParmObj.isString(mnem):
                strLen = self._madParmObj.getStringLen(mnem)
                dataDtype.append((mnem.lower(), numpy.bytes_, strLen))
            else: 
                dataDtype.append((mnem.lower(), float))
            recDType.append((parm.lower(), int))
            recDims.append(2)
            
        # create two recarrays
        self._dataset = numpy.recarray((max(nrow, 1),), dtype = dataDtype)
        self._recordSet = numpy.array([tuple(recDims),], dtype = recDType)
        
        # set prolog values
        sDT = datetime.datetime(int(sYear),int(sMonth),int(sDay),int(sHour),int(sMin),int(sSec),int(sCentisec)*10000)
        eDT = datetime.datetime(int(eYear),int(eMonth),int(eDay),int(eHour),int(eMin),int(eSec),int(eCentisec)*10000)
        midDT = sDT + ((eDT-sDT)/2)

        self._dataset['year'] = midDT.year
        self._dataset['month'] = midDT.month
        self._dataset['day'] = midDT.day
        self._dataset['hour'] = midDT.hour
        self._dataset['min'] = midDT.minute
        self._dataset['sec'] = midDT.second
        self._dataset['recno'] = 0
        self._dataset['kindat'] = kindat
        self.setKinst(kinst)
        self._dataset['ut1_unix'] = madrigal.metadata.getUnixUTFromDT(sDT)
        self._dataset['ut2_unix'] = madrigal.metadata.getUnixUTFromDT(eDT)
        # set all other values to default
        for i in range(len(defaultParms), len(dataDtype)):
            if dataDtype[i][1] == float:
                self._dataset[dataDtype[i][0]] = self.missing
            elif dataDtype[i][1] == int:
                self._dataset[dataDtype[i][0]] = self.missing_int
            else:
                # string type only one left
                strLen = self._madParmObj.getStringLen(dataDtype[i][0])
                self._dataset[dataDtype[i][0]] = ' ' * strLen
                
                    
            

    def __get2DValueList__(self, parm):
        """__get2DValueList__ returns a list containing all the 2D values of a given parameter.

        Inputs:

            parm - can be defined as code (integer) or case-insensitive mnemonic string (eg, "Gdalt")


        Outputs: a list containing all the 2D values of a given parameter.  Special values will
                 be given the values 'missing', 'assumed', or 'knownbad'
        """
        retList = []
        nrow = self.getNrow()
        for i in range(nrow):
            retList.append(self.get2D(parm,i))

        return(retList)


    def __get2DMainValueList__(self, code, scaleFactor):
        """__get2DMainValueList__ returns a list containing all the 2D values of a given main parameter.

        Inputs:

            code - parameter code (integer).  Must
                   be a parameter with an additional increment parameter.


        Outputs: a list containing all the 2D values of a given main parameter that has an
                 additional increment parameter.  Special values will be given the values 'missing', 'assumed', or 'knownbad'
        """
        retList = []
        nrow = self.getNrow()
        for i in range(nrow):
            value = self.get2D(code,i)
            if type(value) != bytes:
                # subtract off additional increment part
                addIncr = value % scaleFactor
                if value < 0:
                    addIncr = -1.0 * (scaleFactor - addIncr)
                value = value - addIncr
            retList.append(value)

        return(retList)


    def __get2DIncrValueList__(self, code, scaleFactor):
        """__get2DIncrValueList__ returns a list containing all the additional increment 2D values of a given main parameter.

        Inputs:

            parm - parameter code (integer).  Must
                   be a parameter with an additional increment parameter.


        Outputs: a list containing all the additional increment 2D values of a given main parameter.
                 Special values will be given the values 'missing', 'assumed', or 'knownbad'
        """
        retList = []
        nrow = self.getNrow()
        for i in range(nrow):
            value = self.get2D(code,i)
            if type(value) != bytes:
                # get additional increment part
                incr = value % scaleFactor
                if value < 0:
                    incr = -1.0 * (scaleFactor - incr)
                value = incr
            retList.append(value)

        return(retList)


    def __str__(self):
        """ returns a string representation of a MadrigalDataRecord """
        retStr = 'Data record:\n'
        try:
            retStr += 'kinst = %i (%s)\n' % (self.getKinst(), self._instrumentName)
        except AttributeError:
            # set instrumentName from dataset kinst
            kinst = self.getKinst()
            self.setKinst(kinst)
            retStr += 'kinst = %i (%s)\n' % (self.getKinst(), self._instrumentName)
        retStr += 'kindat = %i\n' % (self.getKindat())
        startTimeList = self.getStartTimeList()
        endTimeList = self.getEndTimeList()
        retStr += 'record start: %04i-%02i-%02i %02i:%02i:%02i.%02i\n' % (tuple(startTimeList))
        retStr += 'record end:   %04i-%02i-%02i %02i:%02i:%02i.%02i\n' % (tuple(endTimeList))
        retStr += 'one-dim parameters:\n'
        for parm in self._oneDList:
            retStr += '\t%s\n' % (str(parm))
        try:
            retStr += '%s\n' % (str(self._oneDData))
        except AttributeError:
            pass # there may not be oneDData
        retStr += 'two-dim parameters:\n'
        for parm in self._twoDList:
            retStr += '\t%s\n' % (str(parm))
        try:
            retStr += '%s\n' % (str(self._twoDData))
        except AttributeError:
            pass # there may not be twoDData

        return(retStr)
    
    
    def cmpDataRec (self):
        """cmpDataRec returns a tuple of:
            1. 0 if catalog, 1 if header, 2 if data
            2.  start datetime
            3.  end datetime
        """
        # compare record start times
        try:
            fList = self.getStartTimeList()
            sDT = datetime.datetime(*fList)
        except:
            sDT = None
        
        typeEnum = None
        thisType = self.getType()
        for i, dataType in  enumerate(('catalog', 'header', 'data')):
            if thisType == dataType:
                typeEnum = i
                break
            
        # compare record stop times
        try:
            fList = self.getEndTimeList()
            eDT = datetime.datetime(*fList)
        except:
            eDT = None
            
        return((typeEnum, sDT, eDT))

        
        

class MadrigalCatalogRecord:
    """MadrigalCatalogRecord holds all the information in a Cedar catalog record."""
    
    def __init__(self,kinst = None,
                 modexp = None,
                 sYear = None, sMonth = None, sDay = None,
                 sHour = None, sMin = None, sSec = None, sCentisec = None,
                 eYear = None, eMonth = None, eDay = None,
                 eHour = None, eMin = None, eSec = None, eCentisec = None,
                 text = None,
                 madInstObj = None, modexpDesc = '',
                 expNotesLines=None):
        """__init__ creates a MadrigalCatalogRecord.
        
        Note: all inputs have default values because there are two ways to populate this structure:
        1) with all inputs from kinst to text when new data is being created, or 
        2) with catalog line list from existing Hdf5 file Experiment Notes metadata, plus non-default inputs

        Inputs:

            kinst - the kind of instrument code.  A warning will be raised if not in instTab.txt.

            modexp - Code to indicate experimental mode employed. Must be a non-negative integer.

            sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec - experiment start time. sCentisec must be 0-99

            eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec - experiment end time. eCentisec must be 0-99

            text - string containing text in catalog record.  Length must be divisible by 80.  No linefeeds
                   allowed.

            madInstObj - a madrigal.metadata.MadrigalInstrument object.  If None, one will be created.
                              Used to verify kinst.
                              
            modexpDesc - string describing the modexp
                              
            expNotesList - a list of all lines in an existing catalog section "Experiment Notes" 
                metadata table.  All the above attributes are parsed from these lines.

        Outputs: None

        Returns: None
        """
        # create any needed Madrigal objects, if not passed in
        if madInstObj is None:
            self._madInstObj = madrigal.metadata.MadrigalInstrument()
        else:
            self._madInstObj = madInstObj
            
        if expNotesLines != None:
            # get all information from this dataset
            self._parseExpNotesLines(expNotesLines)
            
        if not kinst is None:
            # kinst set via catalog record overrides kinst argument
            try:
                self.getKinst()
            except AttributeError:
                self.setKinst(kinst)
        # verify kinst set, or raise error
        try:
            self.getKinst()
        except AttributeError:
            raise ValueError('kinst not set when MadrigalCatalogRecord created - required')

        if not modexp is None:
            self.setModexp(modexp)
        
        if len(modexpDesc) > 0:
            self.setModexpDesc(modexpDesc)

        try:
            self.setTimeLists(sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec,
                              eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec)
        except:
            pass

        if not text is None:
            self.setText(text)
        else:
            self.setText('')

        
    def getType(self):
        """ returns the type 'catalog'"""
        return 'catalog'
    


    def getKinst(self):
        """getKinst returns the kind of instrument code (int) for a given catalog record.

        Inputs: None

        Outputs: the kind of instrument code (int) for a given catalog record.
        """
        return(self._kinst)


    def setKinst(self, kinst):
        """setKinst sets the kind of instrument code (int) for a given catalog record.

        Inputs: kind of instrument code (integer)

        Outputs: None

        Affects: sets the kind of instrument code (int) (self._kinst) for a given catalog record.
        Prints warning if kinst not found in instTab.txt
        """
        kinst = int(kinst)
        # verify  and set kinst
        instList = self._madInstObj.getInstrumentList()
        found = False
        for inst in instList:
            if inst[2] == kinst:
                self._instrumentName = inst[0]
                found = True
                break
        if found == False:
            self._instrumentName = 'Unknown instrument'
            sys.stderr.write('Warning: kinst %i not found in instTab.txt\n' % (kinst))

        self._kinst = kinst

    def getModexp(self):
        """getModexp returns the mode of experiment code (int) for a given catalog record.

        Inputs: None

        Outputs: the mode of experiment code (int) for a given catalog record. Returns -1 if not set
        """
        try:
            return(self._modexp)
        except AttributeError:
            return(-1)

    def setModexp(self, modexp):
        """setModexp sets the mode of experiment code (int) for a given catalog record.

        Inputs: the mode of experiment code (int)

        Outputs: None

        Affects: sets the mode of experiment code (int) (self._modexp)
        """
        self._modexp = int(modexp)
        
        
    def getModexpDesc(self):
        """getModexp returns the description of the mode of experiment code for a given catalog record.

        Inputs: None

        Outputs: the description of the mode of experiment code for a given catalog record (string).
            Returns empty string if not set
        """
        try:
            return(self._modexpDesc)
        except AttributeError:
            return('')

    def setModexpDesc(self, modexpDesc):
        """setModexpDesc sets the description of the mode of experiment code for a given catalog record.

        Inputs: the description mode of experiment code (string)

        Outputs: None

        Affects: sets the description of the mode of experiment code (string) (self._modexpDesc)
        """
        self._modexpDesc = str(modexpDesc)


    def getText(self):
        """getText returns the catalog text.

        Inputs: None

        Outputs: the catalog text.
        """
        return(self._text)
    
    
    def getTextLineCount(self):
        """getTextLineCount returns the number of 80 character lines in self._text
        """
        return(len(self._text) / 80)


    def setText(self, text):
        """setText sets the catalog text.

        Inputs: text: text to be set.  Must be length divisible by 80, and not contain line feeds.

        Outputs: None.

        Affects: sets self._text

        Raise TypeError if problem with test
        """
        if type(text) != str:
            raise TypeError('text must be of type string')

        if len(text) % 80 != 0:
            raise TypeError('text length must be divisible by 80: len is %i' % (len(text)))

        if text.find('\n') != -1:
            raise TypeError('text must not contain linefeed character')

        self._text = text


    def getStartTimeList(self):
        """getStartTimeList returns a tuple containing sYear, sMonth, sDay, sHour, sMin, sSec, and sCentisec

        Inputs: None

        Outputs: a tuple containing sYear, sMonth, sDay, sHour, sMin, sSec, and sCentisec.
        """
        return((self._sYear,
                self._sMonth,
                self._sDay,
                self._sHour,
                self._sMin,
                self._sSec,
                self._sCentisec))


    def getEndTimeList(self):
        """getEndTimeList returns a tuple containing eYear, eMonth, eDay, eHour, eMin, eSec, and eCentisec

        Inputs: None

        Outputs: a tuple containing eYear, eMonth, eDay, eHour, eMin, eSec, and eCentisec.
        """
        return((self._eYear,
                self._eMonth,
                self._eDay,
                self._eHour,
                self._eMin,
                self._eSec,
                self._eCentisec))
    

    def setTimeLists(self, sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec,
                     eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec):
        """setTimeList resets start and end times

        Inputs:

            sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec - experiment start time. sCentisec must be 0-99

            eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec - experiment end time. eCentisec must be 0-99

        Outputs: None

        Affects: sets all time attributes (see code).

        Exceptions: Raises ValueError if startTime > endTime
        """
        # verify times
        sTime = datetime.datetime(sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec*10000)
        eTime = datetime.datetime(eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec*10000)

        if eTime < sTime:
            raise ValueError('Starting time cannot be after ending time')
        
        self._sTime = madrigal.metadata.getMadrigalUTFromDT(sTime)
        self._eTime = madrigal.metadata.getMadrigalUTFromDT(eTime)
        
        self._sYear = sYear
        self._sMonth = sMonth
        self._sDay = sDay
        self._sHour = sHour
        self._sMin = sMin
        self._sSec = sSec
        self._sCentisec = sCentisec

        
        self._eYear = eYear
        self._eMonth = eMonth
        self._eDay = eDay
        self._eHour = eHour
        self._eMin = eMin
        self._eSec = eSec
        self._eCentisec = eCentisec
        
        
    def getLines(self):
        """getLines returns a numpy recarray of the format expected by the "Experiment Notes" dataset
        """
        # templates
        kreccStr = 'KRECC       2001 Catalogue Record, Version 1'
        kinstTempStr = 'KINSTE     %i %s'
        modExpTempStr = 'MODEXP    %i %s'
        byearTempStr = 'IBYRT               %04i Beginning year'
        bmdTempStr = 'IBDTT               %04i Beginning month and day'
        bhmTempStr = 'IBHMT               %04i Beginning UT hour and minute'
        bcsTempStr = 'IBCST               %04i Beginning centisecond'
        eyearTempStr = 'IEYRT               %04i Ending year'
        emdTempStr = 'IEDTT               %04i Ending month and day'
        ehmTempStr = 'IEHMT               %04i Ending UT hour and minute'
        ecsTempStr = 'IECST               %04i Ending centisecond'
        
        
        numLines = int(self.getTextLineCount() + 12) # 8 times lines, KRECC, KINSTE, MODEXP, and final blank
        textArr = numpy.recarray((numLines,), dtype=[('File Notes', '|S80')])
        for i in range(numLines-9):
            if i == 0: 
                textArr[i]['File Notes'] = kreccStr + ' ' * (80 - len(kreccStr))
            elif i == 1:
                kinstName = self._madInstObj.getInstrumentName(self.getKinst())
                kinstStr = kinstTempStr % (self.getKinst(), kinstName)
                if len(kinstStr) > 80:
                    kinstStr = kinstStr[:80]
                try:
                    textArr[i]['File Notes'] = kinstStr + ' ' * (80 - len(kinstStr))
                except:
                    textArr[i]['File Notes'] = kinstStr.encode() + ' '.encode() * (80 - len(kinstStr.encode()))
            elif i == 2:
                modExpStr = modExpTempStr % (self.getModexp(), self.getModexpDesc())
                if len(modExpStr) > 80:
                    modExpStr = modExpStr[:80]
                textArr[i]['File Notes'] = modExpStr + ' ' * (80 - len(modExpStr))
            else:
                textArr[i]['File Notes'] = (self.getText()[(i-3)*80:(i-2)*80]).encode('utf-8')
                
        # finally add time lines
        sYear, sMonth, sDay, sHour, sMin, sSec, sCentisec = self.getStartTimeList()
        eYear, eMonth, eDay, eHour, eMin, eSec, eCentisec = self.getEndTimeList()
        ibdtt = sMonth*100 + sDay
        ibhmt = sHour*100 + sMin
        ibcst = sSec*100 + sCentisec
        iedtt = eMonth*100 + eDay
        iehmt = eHour*100 + eMin
        iecst = eSec*100 + eCentisec
        
        sYearStr = byearTempStr % (sYear)
        textArr[i+1]['File Notes'] = sYearStr + ' ' * (80 - len(sYearStr))
        sMDStr = bmdTempStr % (ibdtt)
        textArr[i+2]['File Notes'] = sMDStr + ' ' * (80 - len(sMDStr))
        sHMStr = bhmTempStr % (ibhmt)
        textArr[i+3]['File Notes'] = sHMStr + ' ' * (80 - len(sHMStr))
        sCSStr = bcsTempStr % (ibcst)
        textArr[i+4]['File Notes'] = sCSStr + ' ' * (80 - len(sCSStr))
        
        eYearStr = eyearTempStr % (eYear)
        textArr[i+5]['File Notes'] = eYearStr + ' ' * (80 - len(eYearStr))
        eMDStr = emdTempStr % (iedtt)
        textArr[i+6]['File Notes'] = eMDStr + ' ' * (80 - len(eMDStr))
        eHMStr = ehmTempStr % (iehmt)
        textArr[i+7]['File Notes'] = eHMStr + ' ' * (80 - len(eHMStr))
        eCSStr = ecsTempStr % (iecst)
        textArr[i+8]['File Notes'] = eCSStr + ' ' * (80 - len(eCSStr))
        textArr[i+9]['File Notes'] = ' ' * 80
        
        return(textArr)
        
        
    def _parseExpNotesLines(self, expNotesLines):
        """_parseExpNotesLines populates all attributes in MadrigalCatalogRecord
        from text from metadata table "Experiment Notes"
        """
        if len(expNotesLines) % 80 != 0:
            raise ValueError('Len of expNotesLines must be divisible by 80, len %i is not' % (len(expNotesLines)))
        
        self._text = '' # init to empty
        self._modexpDesc = ''
        self._modexp = 0
        
        delimiter = ' '
        # default times
        bsec = 0
        bcsec = 0
        esec = 0
        ecsec = 0
        
        for i in range(int(len(expNotesLines) / 80)):
            line = expNotesLines[i*80:(i+1)*80]
            items = line.split()
            if len(items) == 0:
                # blank line
                self.setText(self.getText() + line)
                continue
            elif items[0].upper() == 'KRECC':
                # ignore
                continue
            elif items[0].upper() == 'KINSTE':
                self.setKinst(int(items[1]))
            elif items[0].upper() == 'MODEXP':
                try:
                    self.setModexp(int(items[1]))
                except:
                    self.setModexp(0)
                if len(items) > 2:
                    self.setModexpDesc(delimiter.join(items[2:]))
                    
            # start time
            elif items[0].upper() == 'IBYRE':
                byear = int(items[1])
            elif items[0].upper() == 'IBDTE':
                ibdte = int(items[1])
                bmonth = ibdte / 100
                bday = ibdte % 100
            elif items[0].upper() == 'IBHME':
                ibhme = int(items[1])
                bhour = ibhme / 100
                bmin = ibhme % 100
            elif items[0].upper() == 'IBCSE':
                ibcse = int(float(items[1]))
                bsec = ibcse / 100
                bcsec = ibcse % 100
                
            # end time
            elif items[0].upper() == 'IEYRE':
                eyear = int(items[1])
            elif items[0].upper() == 'IEDTE':
                iedte = int(items[1])
                emonth = iedte / 100
                eday = iedte % 100
            elif items[0].upper() == 'IEHME':
                iehme = int(items[1])
                ehour = iehme / 100
                emin = iehme % 100
            elif items[0].upper() == 'IECSE':
                iecse = int(float(items[1]))
                esec = iecse / 100
                ecsec = iecse % 100
                
            else:
                self.setText(self.getText() + line)
                    
        try:
            # set times
            self.setTimeLists(byear, bmonth, bday, bhour, bmin, bsec, bcsec, 
                              eyear, emonth, eday, ehour, emin, esec, ecsec)
        except:
            pass
        
        
    def __str__(self):
        """ returns a string representation of a MadrigalCatalogRecord """
        retStr = 'Catalog Record:\n'
        retStr += 'kinst = %i (%s)\n' % (self._kinst, self._instrumentName)
        retStr += 'modexp = %i\n' % (self._modexp)
        retStr += 'record start: %04i-%02i-%02i %02i:%02i:%02i.%02i\n' % (self._sYear,
                                                                        self._sMonth,
                                                                        self._sDay,
                                                                        self._sHour,
                                                                        self._sMin,
                                                                        self._sSec,
                                                                        self._sCentisec)
        retStr += 'record end:   %04i-%02i-%02i %02i:%02i:%02i.%02i\n' % (self._eYear,
                                                                        self._eMonth,
                                                                        self._eDay,
                                                                        self._eHour,
                                                                        self._eMin,
                                                                        self._eSec,
                                                                        self._eCentisec)
        for i in range(0, len(self._text) -1, 80):
            retStr += '%s\n' % (self._text[i:i+80])

        return(retStr)
    
    
    def cmpDataRec (self):
        """cmpDataRec returns a tuple of:
            1. 0 if catalog, 1 if header, 2 if data
            2.  start datetime
            3.  end datetime
        """
        # compare record start times
        try:
            fList = self.getStartTimeList()
            sDT = datetime.datetime(*fList)
        except:
            sDT = None
        
        typeEnum = None
        thisType = self.getType()
        for i, dataType in  enumerate(('catalog', 'header', 'data')):
            if thisType == dataType:
                typeEnum = i
                break
            
        # compare record stop times
        try:
            fList = self.getEndTimeList()
            eDT = datetime.datetime(*fList)
        except:
            eDT = None
            
        return((typeEnum, sDT, eDT))

    

class MadrigalHeaderRecord:
    """MadrigalHeaderRecord holds all the information in a Cedar header record."""
    
    def __init__(self, kinst = None,
                 kindat = None,
                 sYear = None, sMonth = None, sDay = None,
                 sHour = None, sMin = None, sSec = None, sCentisec = None,
                 eYear = None, eMonth = None, eDay = None,
                 eHour = None, eMin = None, eSec = None, eCentisec = None,
                 jpar = None, mpar = None,
                 text = None,
                 madInstObj = None, madKindatObj = None,
                 expNotesLines=None):
        """__init__ creates a MadrigalCatalogRecord.
        
        Note: all inputs have default values because there are two ways to populate this structure:
        1) with all inputs from kinst to text when new data is being created, or 
        2) with catalog line list from existing Hdf5 file Experiment Notes metadata, plus non-default inputs

        Inputs:

            kinst - the kind of instrument code.  A warning will be raised if not in instTab.txt.

            kindat - kind of data code. Must be a non-negative integer.

            sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec - experiment start time. sCentisec must be 0-99

            eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec - experiment end time. eCentisec must be 0-99

            jpar - the number of 1d parameters in the following data records

            mpar - the number of 2d parameters in the following data records

            text - string containing text in catalog record.  Length must be divisible by 80.  No linefeeds
                   allowed.

            madInstObj - a madrigal.metadata.MadrigalInstrument object.  If None, one will be created.
                              Used to verify kinst.
                              
            madKindatObj - a madrigal.metadata.MadrigalKindat onject. If none, one will be created.
                            Used to verify kindat.
                              
            expNotesList - a list of all lines in an existing header section in "Experiment Notes" 
                metadata table.  All the above attributes are parsed from these lines.

        Outputs: None

        Returns: None
        """
        # create any needed Madrigal objects, if not passed in
        if madInstObj is None:
            self._madInstObj = madrigal.metadata.MadrigalInstrument()
        else:
            self._madInstObj = madInstObj
        if madKindatObj is None:
            self._madKindatObj = madrigal.metadata.MadrigalKindat()
        else:
            self._madKindatObj = madKindatObj
            
        if expNotesLines != None:
            # get all information from this dataset
            self._parseExpNotesLines(expNotesLines)

        if not kinst is None:
            # kinst set via header record overrides kinst argument
            try:
                self.getKinst()
            except AttributeError:
                self.setKinst(kinst)
        # verify kinst set, or raise error
        try:
            self.getKinst()
        except AttributeError:
            raise ValueError('kinst not set when MadrigalHeaderRecord created - required')

        if not kindat is None:
            # kindat set via header record overrides kindat argument
            try:
                self.getKindat()
            except AttributeError:
                self.setKindat(kindat)

        try:
            self.setTimeLists(sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec,
                              eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec)
        except:
            pass

        if not jpar is None:
            self.setJpar(jpar)

        if not mpar is None:
            self.setMpar(mpar)

        if not text is None:
            self.setText(text)

        
    def getType(self):
        """ returns the type 'header'"""
        return 'header'


    

    def getKinst(self):
        """getKinst returns the kind of instrument code (int) for a given header record.

        Inputs: None

        Outputs: the kind of instrument code (int) for a given header record.
        """
        return(self._kinst)


    def setKinst(self, kinst):
        """setKinst sets the kind of instrument code (int) for a given header record.

        Inputs: kind of instrument code (integer)

        Outputs: None

        Affects: sets the kind of instrument code (int) (self._kinst) for a given header record.
        Prints warning if kinst not found in instTab.txt
        """
        kinst = int(kinst)
        # verify  and set kinst
        instList = self._madInstObj.getInstrumentList()
        found = False
        for inst in instList:
            if inst[2] == kinst:
                self._instrumentName = inst[0]
                found = True
                break
        if found == False:
            self._instrumentName = 'Unknown instrument'
            sys.stderr.write('Warning: kinst %i not found in instTab.txt\n' % (kinst))

        self._kinst = kinst


    def getKindat(self):
        """getKindat returns the kind of data code (int) for a given header record.

        Inputs: None

        Outputs: the kind of data code (int) for a given header record.
        """
        return(self._kindat)
    
    
    def setKindat(self, kindat):
        """setKindat sets the mode of kind of data code (int) for a given header record.

        Inputs: the kind of data code (int)

        Outputs: None

        Affects: sets the kind of data code (int) (self._kindat)

        Exceptions: Raises ValueError if kindat less than 0
        """
        self._kindat = int(kindat)
        if self._kindat < 0:
            raise ValueError('kindat must not be less than 0, not %i' % (self._kindat))

    def getText(self):
        """getText returns the header text.

        Inputs: None

        Outputs: the header text.
        """
        return(self._text)
    
    
    def getTextLineCount(self):
        """getTextLineCount returns the number of 80 character lines in self._text
        """
        if len(self._text) % 80 == 0:
            return(int(len(self._text) / 80))
        else:
            return(int(1 + int(len(self._text) / 80)))
    

    def setText(self, text):
        """setText sets the header text.

        Inputs: text: text to be set.  Must be length divisible by 80, and not contain line feeds.
        For now, must not exceed 2^16 - 80 bytes to be able to be handled by Cedar format.

        Outputs: None.

        Affects: sets self._text

        Raises TypeError if problem with text
        """
        textTypes = [str]
        if type(text) not in textTypes:
            raise TypeError('text must be of type string')

        if len(text) % 80 != 0:
            raise TypeError('text length must be divisible by 80: len is %i' % (len(text)))

        if text.find('\n') != -1:
            raise TypeError('text must not contain linefeed character')

        if len(text) > 65536 - 80:
            raise TypeError('text exceeds ability of Cedar format to store')

        self._text = text


    def getJpar(self):
        """returns the number of one-dimensional parameters in the associated data records.
        """
        return self._jpar


    def setJpar(self, jpar):
        """ set the number of one-dimensional parameters in the associated data records.

        Must not be negative.
        """
        self._jpar = int(jpar)
        if self._jpar < 0:
            raise TypeError('jpar must not be less than 0')


    def getMpar(self):
        """returns the number of two-dimensional parameters in the associated data records.
        """
        return self._mpar
        

    def setMpar(self, mpar):
        """ set the number of two-dimensional parameters in the associated data records.

        Must not be negative.
        """
        self._mpar = int(mpar)
        if self._mpar < 0:
            raise TypeError('mpar must not be less than 0')


    def getStartTimeList(self):
        """getStartTimeList returns a tuple containing sYear, sMonth, sDay, sHour, sMin, sSec, and sCentisec

        Inputs: None

        Outputs: a tuple containing sYear, sMonth, sDay, sHour, sMin, sSec, and sCentisec.
        """
        return((self._sYear,
                self._sMonth,
                self._sDay,
                self._sHour,
                self._sMin,
                self._sSec,
                self._sCentisec))


    def getEndTimeList(self):
        """getEndTimeList returns a tuple containing eYear, eMonth, eDay, eHour, eMin, eSec, and eCentisec

        Inputs: None

        Outputs: a tuple containing eYear, eMonth, eDay, eHour, eMin, eSec, and eCentisec.
        """
        return((self._eYear,
                self._eMonth,
                self._eDay,
                self._eHour,
                self._eMin,
                self._eSec,
                self._eCentisec))
        
        
    def getLines(self):
        """getLines returns a numpy recarray of the format expected by the "Experiment Notes" dataset
        """
        # templates
        krechStr = 'KRECH               3002 Header Record, Version 3'
        kinstTempStr = 'KINST     %i %s'
        kindatTempStr = 'KINDAT    %i %s'
        byearTempStr = 'IBYRT               %04i Beginning year'
        bmdTempStr = 'IBDTT               %04i Beginning month and day'
        bhmTempStr = 'IBHMT               %04i Beginning UT hour and minute'
        bcsTempStr = 'IBCST               %04i Beginning centisecond'
        eyearTempStr = 'IEYRT               %04i Ending year'
        emdTempStr = 'IEDTT               %04i Ending month and day'
        ehmTempStr = 'IEHMT               %04i Ending UT hour and minute'
        ecsTempStr = 'IECST               %04i Ending centisecond'
        
        numLines = int(self.getTextLineCount() + 12) # 8 times lines, KRECH, KINST, KINDAT, and final blank
        textArr = numpy.recarray((numLines,), dtype=[('File Notes', '|S80')])
        for i in range(numLines-9):
            if i == 0: 
                textArr[i]['File Notes'] = krechStr + ' ' * (80 - len(krechStr))
            elif i == 1:
                kinstName = self._madInstObj.getInstrumentName(self.getKinst())
                kinstStr = kinstTempStr % (self.getKinst(), kinstName)
                if len(kinstStr) > 80:
                    kinstStr = kinstStr[:80]
                try:
                    textArr[i]['File Notes'] = kinstStr + ' ' * (80 - len(kinstStr))
                except:
                    textArr[i]['File Notes'] = kinstStr.encode() + ' '.encode() * (80 - len(kinstStr.encode()))
            elif i == 2:
                kindatStr = kindatTempStr % (self.getKindat(), 
                                             self._madKindatObj.getKindatDescription(self.getKindat(),
                                                                                     self.getKinst()))
                if len(kindatStr) > 80:
                    kindatStr = kindatStr[:80]
                textArr[i]['File Notes'] = kindatStr + ' ' * (80 - len(kindatStr))
            else:
                textArr[i]['File Notes'] = self.getText()[(i-3)*80:(i-2)*80]
                
        # finally add time lines
        sYear, sMonth, sDay, sHour, sMin, sSec, sCentisec = self.getStartTimeList()
        eYear, eMonth, eDay, eHour, eMin, eSec, eCentisec = self.getEndTimeList()
        ibdtt = sMonth*100 + sDay
        ibhmt = sHour*100 + sMin
        ibcst = sSec*100 + sCentisec
        iedtt = eMonth*100 + eDay
        iehmt = eHour*100 + eMin
        iecst = eSec*100 + eCentisec
        
        sYearStr = byearTempStr % (sYear)
        textArr[i+1]['File Notes'] = sYearStr + ' ' * (80 - len(sYearStr))
        sMDStr = bmdTempStr % (ibdtt)
        textArr[i+2]['File Notes'] = sMDStr + ' ' * (80 - len(sMDStr))
        sHMStr = bhmTempStr % (ibhmt)
        textArr[i+3]['File Notes'] = sHMStr + ' ' * (80 - len(sHMStr))
        sCSStr = bcsTempStr % (ibcst)
        textArr[i+4]['File Notes'] = sCSStr + ' ' * (80 - len(sCSStr))
        
        eYearStr = eyearTempStr % (eYear)
        textArr[i+5]['File Notes'] = eYearStr + ' ' * (80 - len(eYearStr))
        eMDStr = emdTempStr % (iedtt)
        textArr[i+6]['File Notes'] = eMDStr + ' ' * (80 - len(eMDStr))
        eHMStr = ehmTempStr % (iehmt)
        textArr[i+7]['File Notes'] = eHMStr + ' ' * (80 - len(eHMStr))
        eCSStr = ecsTempStr % (iecst)
        textArr[i+8]['File Notes'] = eCSStr + ' ' * (80 - len(eCSStr))
        textArr[i+9]['File Notes'] = ' ' * 80
        
        return(textArr)

    
    def setTimeLists(self, sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec,
                     eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec):
        """setTimeList resets start and end times

        Inputs:

            sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec - experiment start time. sCentisec must be 0-99

            eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec - experiment end time. eCentisec must be 0-99

        Outputs: None

        Affects: sets all time attributes (see code).

        Exceptions: Raises ValueError if startTime > endTime
        """
        # verify times
        sTime = datetime.datetime(sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec*10000)
        eTime = datetime.datetime(eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec*10000)

        if eTime < sTime:
            raise ValueError('Starting time cannot be after ending time')
        
        self._sTime = madrigal.metadata.getMadrigalUTFromDT(sTime)
        self._eTime = madrigal.metadata.getMadrigalUTFromDT(eTime)
        
        self._sYear = sYear
        self._sMonth = sMonth
        self._sDay = sDay
        self._sHour = sHour
        self._sMin = sMin
        self._sSec = sSec
        self._sCentisec = sCentisec

        
        self._eYear = eYear
        self._eMonth = eMonth
        self._eDay = eDay
        self._eHour = eHour
        self._eMin = eMin
        self._eSec = eSec
        self._eCentisec = eCentisec
        
        
    def _parseExpNotesLines(self, expNotesLines):
        """_parseExpNotesLines populates all attributes in MadrigalHeaderRecord
        from text from metadata table "Experiment Notes"
        """
        if len(expNotesLines) % 80 != 0:
            raise ValueError('Len of expNotesLines must be divisible by 80, len %i is not' % (len(expNotesLines)))
        
        self._text = '' # init to empty
        
        delimiter = ' '
        # default times
        byear = None # to verify lines found
        addItem = 0 # check for the case where there is a addition item in front of date field
        bsec = 0
        bcsec = 0
        esec = 0
        ecsec = 0
        for i in range(int(len(expNotesLines) / 80)):
            line = expNotesLines[i*80:(i+1)*80]
            items = line.split()
            if len(items) == 0:
                # blank line
                self.setText(self.getText() + line)
                continue
            elif items[0].upper() == 'KRECH':
                # ignore
                continue
            elif items[0].upper() == 'KINST':
                if int(items[1]) != 3:
                    self.setKinst(int(items[1]))
                else:
                    self.setKinst(int(items[2]))
            elif items[0].upper() == 'KINDAT':
                try:
                    if int(items[1]) != 4:
                        self.setKindat(int(items[1]))
                    else:
                        self.setKindat(int(items[2]))
                except:
                    self.setKindat(0)
                    
            # start time
            elif items[0].upper() == 'IBYRT':
                byear = int(items[1+addItem])
                if byear < 1950:
                    # wrong column parsed
                    addItem = 1
                    byear = int(items[1+addItem])
                
            elif items[0].upper() in ('IBDTT', 'IBDT'):
                ibdte = int(items[1+addItem])
                bmonth = ibdte / 100
                bday = ibdte % 100
            elif items[0].upper() == 'IBHMT':
                ibhme = int(items[1+addItem])
                bhour = ibhme / 100
                bmin = ibhme % 100
            elif items[0].upper() == 'IBCST':
                ibcse = int(float(items[1+addItem]))
                bsec = ibcse / 100
                bcsec = ibcse % 100
                
            # end time
            elif items[0].upper() == 'IEYRT':
                eyear = int(items[1+addItem])
            elif items[0].upper() in ('IEDTT', 'IEDT'):
                iedte = int(items[1+addItem])
                emonth = iedte / 100
                eday = iedte % 100
            elif items[0].upper() == 'IEHMT':
                iehme = int(items[1+addItem])
                ehour = iehme / 100
                emin = iehme % 100
            elif items[0].upper() == 'IECST':
                iecse = int(float(items[1+addItem]))
                esec = iecse / 100
                ecsec = iecse % 100
                
            else:
                self.setText(self.getText() + line)
                    
        try:
            # set times
            self.setTimeLists(byear, bmonth, bday, bhour, bmin, bsec, bcsec, 
                              eyear, emonth, eday, ehour, emin, esec, ecsec)
        except:
            pass
        
    
    def __str__(self):
        """ returns a string representation of a MadrigalHeaderRecord """
        retStr = 'Header Record:\n'
        retStr += 'kinst = %i (%s)\n' % (self._kinst, self._instrumentName)
        retStr += 'kindat = %i\n' % (self._kindat)
        retStr += 'record start: %04i-%02i-%02i %02i:%02i:%02i.%02i\n' % (self._sYear,
                                                                        self._sMonth,
                                                                        self._sDay,
                                                                        self._sHour,
                                                                        self._sMin,
                                                                        self._sSec,
                                                                        self._sCentisec)
        retStr += 'record end:   %04i-%02i-%02i %02i:%02i:%02i.%02i\n' % (self._eYear,
                                                                        self._eMonth,
                                                                        self._eDay,
                                                                        self._eHour,
                                                                        self._eMin,
                                                                        self._eSec,
                                                                        self._eCentisec)
        
        retStr += 'jpar = %i, mpar = %i' % (self._jpar, self._mpar)
        
        for i in range(0, len(self._text) -1, 80):
            retStr += '%s\n' % (self._text[i:i+80])

        return(retStr)
    
    
    def cmpDataRec (self):
        """cmpDataRec returns a tuple of:
            1. 0 if catalog, 1 if header, 2 if data
            2.  start datetime
            3.  end datetime
        """
        # compare record start times
        try:
            fList = self.getStartTimeList()
            sDT = datetime.datetime(*fList)
        except:
            sDT = None
        
        typeEnum = None
        thisType = self.getType()
        for i, dataType in  enumerate(('catalog', 'header', 'data')):
            if thisType == dataType:
                typeEnum = i
                break
            
        # compare record stop times
        try:
            fList = self.getEndTimeList()
            eDT = datetime.datetime(*fList)
        except:
            eDT = None
            
        return((typeEnum, sDT, eDT))



class CatalogHeaderCreator:
    """CatalogHeaderCreator is a class that automates the creation of catalog and header records
    
    This class creates and adds catalog and header records that meet the Cedar standards.  It does this 
    by examining the input Cedar file for all summary information possible.  The user needs only 
    add text that describes their experiment.  A Cedar file must already be written to disk before
    this class is created.
    """
    def __init__(self, madFilename):
        """__init__ reads in all summary information about madFilename using madrigal.data
        """
        self._madFilename = madFilename
        self._summary = madrigal.data.MadrigalFile(self._madFilename)
        self._cedar = MadrigalCedarFile(madFilename, maxRecords=3) # parse small part of file into MadrigalCedarFile object
        # create default header and catalog records
        self._header = None
        self._catalog = None
        self._lineLen = 80
        
        
    def createCatalog(self, principleInvestigator=None,
                      expPurpose=None,
                      expMode=None,
                      cycleTime=None,
                      correlativeExp=None,
                      sciRemarks=None,
                      instRemarks=None):
        """createCatalog will create a catalog record appropriate for this file.  The additional
        information fields are all optional, and are all simple text strings (except for
        cycleTime, which is in minutes).  If the text contains line feeds, those will be used 
        as line breaks in the catalog record.
        
        The descriptions of these fields all come from Barbara Emery's documentation
        cedarFormat.pdf
        
        Inputs:
        
            principleInvestigator - Names of responsible Principal Investigator(s) or others knowledgeable 
                                    about the experiment.
            
            expPurpose - Brief description of the experiment purpose
            
            expMode - Further elaboration of meaning of MODEXP; e.g. antenna patterns and 
                      pulse sequences.
                      
            cycleTime - Minutes for one full measurement cycle
            
            correlativeExp - Correlative experiments (experiments with related data)
            
            sciRemarks - scientific remarks
            
            instRemarks - instrument remarks
            
        Returns: None
        
        Affects: sets self._catalog
        """
        # the first step is to create the text part
        text = ''
        
        # start with parameter summary lines
        if cycleTime != None:
            text += 'TIMCY  %9i minutes' % (int(cycleTime))
            text = self._padStr(text, self._lineLen)
            
        text += self._createMaxMinSummaryLines()
        
        # add the time lines
        text += self._createCatalogTimeSection()[0]
        
        # then add any text from input arguments
        if expMode != None:
            text += self._createCedarLines('CMODEXP ', expMode)
            
        if expPurpose != None:
            text += self._createCedarLines('CPURP   ', expPurpose)
            
        if correlativeExp != None:
            text += self._createCedarLines('CCOREXP ', correlativeExp)
            
        if sciRemarks != None:
            text += self._createCedarLines('CSREM   ', sciRemarks)
            
        if instRemarks != None:
            text += self._createCedarLines('CIREM   ', instRemarks)
            
        if principleInvestigator != None:
            text += self._createCedarLines('CPI     ', principleInvestigator)
            
        # get some other metadata
        kinst = self._summary.getKinstList()[0]
        modexp = self._summary.getKindatList()[0]
        sYear,sMonth,sDay,sHour,sMin,sSec = self._summary.getEarliestTime()
        sCentisec = 0
        eYear,eMonth,eDay,eHour,eMin,eSec = self._summary.getLatestTime()
        eCentisec = 0
        
        # now create the catalog record
        self._catalog = MadrigalCatalogRecord(kinst, modexp,
                                              sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec,
                                              eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec,
                                              text)
        
        
    def createHeader(self, kindatDesc=None, 
                           analyst=None, 
                           comments=None, 
                           history=None):
        """createHeader will create a header record appropriate for this file.  The additional
        information fields are all optional, and are all simple text strings.  If the text contains l
        ine feeds, those will be used as line breaks in the header record.
        
        Inputs:
        
            kindatDesc - description of how this data was analyzed (the kind of data)
            
            analyst - name of person who analyzed this data
            
            comments - additional comments about data (describe any instrument-specific parameters) 
            
            history - a description of the history of the processing of this file
            
        Returns: None
        
        Affects: sets self._header
        """
        # the first step is to create the text part
        text = ''
        
        if kindatDesc != None:
            text += self._createCedarLines('CKINDAT', kindatDesc)
            
        if history != None:
            text += self._createCedarLines('CHIST  ', history)
            
        # add the time lines
        text += self._createHeaderTimeSection()[0]
        
        # add the KOD linesfrom the last record of file (must be data record)
        text += self._cedar[-1].getHeaderKodLines()
        
        if comments != None:
            text += self._createCedarLines('C      ', comments)
            
        if analyst != None:
            text += self._createCedarLines('CANALYST', analyst)
            
        # last - time of analysis line
        now = datetime.datetime.utcnow()
        nowStr = now.strftime('%a %b %d %H:%M:%S %Y')
        text += 'CANDATE  %s UT' % (nowStr)
        text = self._padStr(text, self._lineLen)
        
        # get some other metadata
        kinst = self._summary.getKinstList()[0]
        kindat = self._summary.getKindatList()[0]
        sYear,sMonth,sDay,sHour,sMin,sSec = self._summary.getEarliestTime()
        sCentisec = 0
        eYear,eMonth,eDay,eHour,eMin,eSec = self._summary.getLatestTime()
        eCentisec = 0
        jpar = len(self._cedar[-1].get1DParms())
        mpar = len(self._cedar[-1].get2DParms())
        
        self._header = MadrigalHeaderRecord(kinst, kindat,
                                            sYear,sMonth,sDay,sHour,sMin,sSec,sCentisec,
                                            eYear,eMonth,eDay,eHour,eMin,eSec,eCentisec,
                                            jpar, mpar, text)
        
        
    def write(self, newFilename=None):
        """write will output the new file with prepended catalog and header records
        
        Raises an IOError if no new catalog or header records to prepend
        
        Inputs:
        
            newFilename - if None, overwrite original file
        """
        if self._catalog is None and self._header is None:
            raise IOError('Does not make sense to save a new file if no catalog or header has been added')
        
        if self._header != None:
            self._cedar.insert(0, self._header)
            
        if self._catalog != None:
            self._cedar.insert(0, self._catalog)
            
        if newFilename is None:
            newFilename = self._madFilename
        else:
            shutil.copy(self._madFilename, newFilename)
            
        # open file for appening
        with h5py.File(newFilename, 'a') as f:
            metadata = f['Metadata']
            self._cedar.writeExperimentNotes(metadata, False)

        
        
        
    def _createCatalogTimeSection(self):
        """_createCatalogTimeSection will return all the lines in the catalog record that
        describe the start and end time of the data records.

        Inputs: None

        Returns:  a tuple with three items 1) a string in the format of the time section of a
        catalog record, 2) earliest datetime, 3) latest datetime
        """

        earliestStartTimeList = self._summary.getEarliestTime()
        earliestStartTime = datetime.datetime(*earliestStartTimeList)
        latestEndTimeList = self._summary.getLatestTime()
        latestEndTime = datetime.datetime(*latestEndTimeList)

        sy = 'IBYRE       %4s Beginning year' % (str(earliestStartTime.year))
        sd = 'IBDTE       %4s Beginning month and day' % (str(earliestStartTime.month*100 + \
                                                              earliestStartTime.day))
        sh = 'IBHME       %4s Beginning UT hour and minute' % (str(earliestStartTime.hour*100 + \
                                                                   earliestStartTime.minute))
        totalCS = earliestStartTime.second*100 + (earliestStartTime.microsecond/10000)
        ss = 'IBCSE       %4s Beginning centisecond'  % (str(totalCS))
        
        ey = 'IEYRE       %4s Ending year' % (str(latestEndTime.year))
        ed = 'IEDTE       %4s Ending month and day' % (str(latestEndTime.month*100 + \
                                                           latestEndTime.day))
        eh = 'IEHME       %4s Ending UT hour and minute' % (str(latestEndTime.hour*100 + \
                                                                latestEndTime.minute))
        totalCS = latestEndTime.second*100 + (latestEndTime.microsecond/10000)
        es = 'IECSE       %4s Ending centisecond'  % (str(totalCS))

        retStr = ''
        retStr += sy + (80-len(sy))*' '
        retStr += sd + (80-len(sd))*' '
        retStr += sh + (80-len(sh))*' '
        retStr += ss + (80-len(ss))*' '
        retStr += ey + (80-len(ey))*' '
        retStr += ed + (80-len(ed))*' '
        retStr += eh + (80-len(eh))*' '
        retStr += es + (80-len(es))*' '

        return((retStr, earliestStartTime, latestEndTime))
    
    
    def _createHeaderTimeSection(self, dataRecList=None):
        """_createHeaderTimeSection will return all the lines in the header record that
        describe the start and end time of the data records.

        Inputs:

            dataRecList - if given, examine only those MadrigalDataRecords in dataRecList.
                          If None (the default), examine all MadrigalDataRecords in this
                          MadrigalCedarFile

        Returns:  a tuple with three items 1) a string in the format of the time section of a
        header record, 2) earliest datetime, 3) latest datetime
        """
        earliestStartTimeList = self._summary.getEarliestTime()
        earliestStartTime = datetime.datetime(*earliestStartTimeList)
        latestEndTimeList = self._summary.getLatestTime()
        latestEndTime = datetime.datetime(*latestEndTimeList)
                

        sy = 'IBYRT               %4s Beginning year' % (str(earliestStartTime.year))
        sd = 'IBDTT               %4s Beginning month and day' % (str(earliestStartTime.month*100 + \
                                                              earliestStartTime.day))
        sh = 'IBHMT               %4s Beginning UT hour and minute' % (str(earliestStartTime.hour*100 + \
                                                                   earliestStartTime.minute))
        totalCS = earliestStartTime.second*100 + (earliestStartTime.microsecond/10000)
        ss = 'IBCST               %4s Beginning centisecond'  % (str(totalCS))
        
        ey = 'IEYRT               %4s Ending year' % (str(latestEndTime.year))
        ed = 'IEDTT               %4s Ending month and day' % (str(latestEndTime.month*100 + \
                                                           latestEndTime.day))
        eh = 'IEHMT               %4s Ending UT hour and minute' % (str(latestEndTime.hour*100 + \
                                                                latestEndTime.minute))
        totalCS = latestEndTime.second*100 + (latestEndTime.microsecond/10000)
        es = 'IECST               %4s Ending centisecond'  % (str(totalCS))

        retStr = ''
        retStr += sy + (80-len(sy))*' '
        retStr += sd + (80-len(sd))*' '
        retStr += sh + (80-len(sh))*' '
        retStr += ss + (80-len(ss))*' '
        retStr += ey + (80-len(ey))*' '
        retStr += ed + (80-len(ed))*' '
        retStr += eh + (80-len(eh))*' '
        retStr += es + (80-len(es))*' '

        return((retStr, earliestStartTime, latestEndTime))
        
        
    
    def _createMaxMinSummaryLines(self):
        """_createMaxMinSummaryLines is a private method that creates the max and min summary 
        lines (e.g., alt, gdlat, etc)
        """
        alt1 = 'ALT1 %11i km. Lowest altitude measured'
        alt2 = 'ALT2 %11i km. Highest altitude measured'
        lat1 = 'GGLAT1    %6i degrees. Lowest geographic latitude measured'
        lat2 = 'GGLAT2    %6i degrees. Highest geographic latitude measured'
        lon1 = 'GGLON1    %6i degrees. Westmost geographic longitude measured'
        lon2 = 'GGLON2    %6i degrees. Eastmost geographic longitude measured'
        pl1 = 'PL1  %11i Shortest radar pulse length'
        pl2 = 'PL2  %11i Longest radar pulse length'
        
        retStr = ''
        
        minAlt = self._summary.getMinValidAltitude()
        maxAlt = self._summary.getMaxValidAltitude()
        if minAlt > 0 and minAlt < 1E9:
            retStr += alt1 % (int(minAlt))
            retStr = self._padStr(retStr, self._lineLen)
            retStr += alt2 % (int(maxAlt))
            retStr = self._padStr(retStr, self._lineLen)
            
        minLat = self._summary.getMinLatitude()
        maxLat = self._summary.getMaxLatitude()
        if minLat > -91 and minLat < 91:
            retStr += lat1 % (int(minLat))
            retStr = self._padStr(retStr, self._lineLen)
            retStr += lat2 % (int(maxLat))
            retStr = self._padStr(retStr, self._lineLen)
            
        minLon = self._summary.getMinLongitude()
        maxLon = self._summary.getMaxLongitude()
        if minLon > -181 and minLon < 360:
            retStr += lon1 % (int(minLon))
            retStr = self._padStr(retStr, self._lineLen)
            retStr += lon2 % (int(maxLon))
            retStr = self._padStr(retStr, self._lineLen)
            
        minPl = self._summary.getMinPulseLength()
        maxPl = self._summary.getMaxPulseLength()
        if minPl > 0.001 and minPl < 10E9:
            retStr += pl1 % (int(minPl))
            retStr = self._padStr(retStr, self._lineLen)
            retStr += pl2 % (int(maxPl))
            retStr = self._padStr(retStr, self._lineLen)
            
        return(retStr)

    
    def _createCedarLines(self, prefix, text):
        """_createCedarLines is a private method that returns a string which is a multiple of 
        80 characters (no line feeds) where each 80 character block starts with prefix,then a space, 
        and then the next part of text that fits on line, padded with spaces
        """
        lineLen = self._lineLen
        if len(prefix) > self._lineLen/2:
            raise IOError('Too long prefix %s' % (str(prefix)))
        retStr = ''
        
        # first check for line feeds
        lines = text.split('\n')
        for line in lines:
            # now split by words
            words = line.split()
            for word in words:
                # see if this word can fit on one line
                if len(word) + 1 > lineLen - len(prefix) + 1:
                    raise IOError('Can not fit the word <%s> in a Cedar text record' % (word))
                # see if there's room for this word
                if (lineLen - (len(retStr) % lineLen) <= len(word) + 1) or \
                (len(retStr) % lineLen == 0):
                    retStr = self._padStr(retStr, lineLen)
                    retStr += '%s ' % (prefix)
                retStr += '%s ' % (word)
            # at line break, we always pad
            retStr = self._padStr(retStr, lineLen)
            
        return(retStr)
    
    def _padStr(self, thisStr, lineLen):
        """_padStr is a private method that pads a string with spaces so its length is module lineLen
        """
        spacesToPad = lineLen - (len(thisStr) % lineLen)
        if spacesToPad == lineLen:
            return(thisStr)
        thisStr += ' ' * spacesToPad
        return(thisStr)
        


class CedarParameter:
    """CedarParameter is a class with attributes code, mnemonic, and description, and isInt"""
    
    def __init__(self, code, mnemonic, description, isInt):
        self.code = int(code)
        self.mnemonic = str(mnemonic)
        self.description = str(description)
        self.isInt = bool(isInt)

    def __str__(self):
        return('%6i: %20s: %s, isInt=%s' % (self.code, self.mnemonic, self.description, str(self.isInt)))
    
    
    
class convertToNetCDF4:
    def __init__(self, inputHdf5, outputNC):
        """convertToNetCDF4 converts a Madrigal HDF5 file to netCDF4 using Array Layout
            rather than using Table Layout as cedar module does.  Can handle large Hdf5 file
            without large memory footprint, and is much faster than reading in using 
            madrigal.cedar.MadrigalCedarFile
            
            Inputs:
                inputHdf5 - filename of input Madrigal Hdf5 file
                outputNC - output netCDF4 file
                
        """
        madParmObj = madrigal.data.MadrigalParameters()
        
        self._fi = h5py.File(inputHdf5, 'r')
        if 'Array Layout' not in self._fi['Data']:
            if os.path.getsize(inputHdf5) < 50000000:
                # for smaller files we simply go through the slower full cedar conversion
                cedarObj = MadrigalCedarFile(inputHdf5)
                cedarObj.write('netCDF4', outputNC)
                return
            else:
                # file is to big to load into memory at once, read only 10 records at once at write to file
                # parm IndexDict is a dictionary with key = timestamps and ind spatial parm names,
                # value = dictionary of keys = unique values, value = index
                # temp only
                total = 0
                t = time.time()
                parmIndexDict = self._getParmIndexDict()
                self._fi.close()
                madCedarObj = madrigal.cedar.MadrigalCedarFile(inputHdf5, maxRecords=10)
                madCedarObj.dump('netCDF4', outputNC, parmIndexDict)
                total += 10
                while (True):
                    # temp only
                    print('%i done so far in %f secs' % (total, time.time()-t))
                    newRecs, isComplete = madCedarObj.loadNextRecords(10)
                    if isComplete:
                        break
                    madCedarObj.dump('netCDF4', outputNC, parmIndexDict)
                    if newRecs < 10:
                        break
                    total += newRecs
                    
                # compress
                filename, file_extension = os.path.splitext(outputNC)
                # tmp file name to use to run h5repack
                tmpFile = filename + '_tmp' + file_extension
                cmd = 'h5repack -i %s -o %s --filter=GZIP=4' % (outputNC, tmpFile)
                try:
                    subprocess.check_call(shlex.split(cmd))
                except:
                    traceback.print_exc()
                    return
                
                shutil.move(tmpFile, outputNC)
                    
                return

        self._fo = netCDF4.Dataset(outputNC, 'w', format='NETCDF4')
        self._fo.catalog_text = self.getCatalogText()
        self._fo.header_text = self.getHeaderText()
        
        # write Experiment Parameters
        experimentParameters = self._fi['Metadata']['Experiment Parameters']
        for i in range(len(experimentParameters)):
            name = experimentParameters['name'][i]
            if type(name) in (bytes, numpy.bytes_):
                name = name.decode("utf8")
            # make text acceptable attribute names
            name = name.replace(' ', '_')
            name = name.replace('(s)', '')
            self._fo.setncattr(name, experimentParameters['value'][i])
            
        indParmListOrg = [parm[0].lower() for parm in self._fi['Metadata']['Independent Spatial Parameters']]
        indParmList = []
        for indParm in indParmListOrg:
            if type(indParm) in (numpy.bytes_, bytes):
                indParmList.append(indParm.decode('utf8'))
            else:
                indParmList.append(indParm)
            
            
        # split parms - if any
        has_split = 'Parameters Used to Split Array Data' in list(self._fi['Metadata'].keys())
        arraySplittingMnemonics = []
        if has_split:
            arraySplittingParms = self._fi['Metadata']['Parameters Used to Split Array Data']
            arrSplitParmDesc = ''
            for i in range(len(arraySplittingParms)):
                arrSplitParmDesc += '%s: ' % (arraySplittingParms[i]['mnemonic'].lower())
                arrSplitParmDesc += '%s' % (arraySplittingParms[i]['description'].lower())
                arraySplittingMnemonic = arraySplittingParms[i]['mnemonic'].lower()
                if type(arraySplittingMnemonic) in (numpy.bytes_, bytes):
                    arraySplittingMnemonic = arraySplittingMnemonic.decode('utf8')
                arraySplittingMnemonics.append(arraySplittingMnemonic)
                if arraySplittingParms[i] != arraySplittingParms[-1]:
                    arrSplitParmDesc += ' -- '
            self._fo.parameters_used_to_split_data = arrSplitParmDesc
            
        if has_split:
            names = list(self._fi['Data']['Array Layout'].keys())
            groups = [self._fi['Data']['Array Layout'][name] for name in names]
        else:
            names = [None]
            groups = [self._fi['Data']['Array Layout']]
            
            
        # loop through each split array (or just top level, if none
        for i in range(len(groups)):
            name = names[i]
            if not name is None:
                nc_name = name.strip().replace(' ', '_')
                thisGroup = self._fo.createGroup(nc_name)
                hdf5Group = self._fi['Data']['Array Layout'][name]
            else:
                thisGroup = self._fo
                hdf5Group = self._fi['Data']['Array Layout']
                
            times = hdf5Group['timestamps']
                
            # next step - create dimensions
            dims = []
            
            # first time dim
            thisGroup.createDimension("timestamps", len(times))
            timeVar = thisGroup.createVariable("timestamps", 'f8', ("timestamps",),
                                               zlib=True)
            timeVar.units = 'Unix seconds'
            timeVar.description = 'Number of seconds since UT midnight 1970-01-01'
            timeVar[:] = times
            dims.append("timestamps")
            
            # next ind parms, because works well with ncview that way
            for indParm in indParmList:
                this_name = indParm
                if this_name[0] == '-':
                    this_name = 'neg' + this_name
                if indParm in arraySplittingMnemonics:
                    continue
                thisGroup.createDimension(indParm, len(hdf5Group[indParm]))
                if madParmObj.isInteger(indParm):
                    thisVar = thisGroup.createVariable(this_name, 'i8', (indParm,),
                                                       zlib=True)
                    thisVar[:] = hdf5Group[indParm]
                elif madParmObj.isString(indParm):
                    slen = len(hdf5Group[indParm][0])
                    dtype = 'S%i' % (slen)
                    thisVar = thisGroup.createVariable(this_name, dtype, (indParm,),
                                                       zlib=True)
                    for i in range(len(hdf5Group[indParm])):
                        thisVar[i] = str(hdf5Group[indParm][i])
                else:
                    thisVar = thisGroup.createVariable(this_name, 'f8', (indParm,),
                                                       zlib=True)
                    thisVar[:] = hdf5Group[indParm]
                thisVar.units = madParmObj.getParmUnits(indParm)
                thisVar.description = madParmObj.getSimpleParmDescription(indParm)
                dims.append(indParm)
                
            
                
            # get all one d data
            oneDParms = list(hdf5Group['1D Parameters'].keys())
            for oneDParm in oneDParms:
                this_name = oneDParm
                if this_name[0] == '-':
                    this_name = 'neg' + this_name
                if type(oneDParm) in (numpy.bytes_, bytes):
                    oneDParm = oneDParm.decode('utf8')
                if oneDParm in indParmList:
                    if oneDParm not in arraySplittingMnemonics:
                        continue
                if oneDParm.find('Data Parameters') != -1:
                    continue
                if madParmObj.isInteger(oneDParm):
                    oneDVar = thisGroup.createVariable(this_name, 'i8', (dims[0],),
                                                       zlib=True)
                elif madParmObj.isString(oneDParm):
                    slen = len(hdf5Group['1D Parameters'][oneDParm][0])
                    dtype = 'S%i' % (slen)
                    oneDVar = thisGroup.createVariable(this_name, dtype, (dims[0],),
                                                       zlib=True)
                else:
                    oneDVar = thisGroup.createVariable(this_name, 'f8', (dims[0],),
                                                       zlib=True)
                oneDVar.units = madParmObj.getParmUnits(oneDParm)
                oneDVar.description = madParmObj.getSimpleParmDescription(oneDParm)
                try:
                    oneDVar[:] = hdf5Group['1D Parameters'][oneDParm]
                except:
                    oneDVar[:] = hdf5Group['1D Parameters'][oneDParm][()]
                
                
            # get all two d data
            twoDParms = list(hdf5Group['2D Parameters'].keys())
            for twoDParm in twoDParms:
                this_name = twoDParm
                if this_name[0] == '-':
                    this_name = 'neg' + this_name
                if type(twoDParm) in (numpy.bytes_, bytes):
                    twoDParm = twoDParm.decode('utf8')
                if twoDParm.find('Data Parameters') != -1:
                    continue
                if twoDParm in indParmList:
                    if twoDParm not in arraySplittingMnemonics:
                        continue
                if madParmObj.isInteger(twoDParm):
                    twoDVar = thisGroup.createVariable(this_name, 'i8', dims,
                                                       zlib=True)
                elif madParmObj.isString(twoDParm):
                    slen = len(hdf5Group['2D Parameters'][twoDParm][0])
                    dtype = 'S%i' % (slen)
                    twoDVar = thisGroup.createVariable(this_name, dtype, dims,
                                                       zlib=True)
                else:
                    twoDVar = thisGroup.createVariable(this_name, 'f8', dims,
                                                       zlib=True)
                twoDVar.units = madParmObj.getParmUnits(twoDParm)
                twoDVar.description = madParmObj.getSimpleParmDescription(twoDParm)
                # move the last dim in Hdf5 (time) to be the first now
                reshape = list(range(len(dims)))
                newShape = reshape[-1:] + reshape[0:-1]
                data = numpy.transpose(hdf5Group['2D Parameters'][twoDParm], newShape)
                twoDVar[:] = data
                data = None
            
                
        
        self._fo.close()
        self._fi.close()
        
        
    def getCatalogText(self):
        """getCatalogText returns the catalog record text as a string
        """
        if not 'Experiment Notes' in list(self._fi['Metadata'].keys()):
            return('')
        notes = self._fi['Metadata']['Experiment Notes']
        retStr = ''
        for substr in notes:
            if type(substr[0]) in (numpy.bytes_, bytes):
                if substr[0].find(b'Header information') != -1:
                    break
            else:
                if substr[0].find('Header information') != -1:
                    break
            if type(substr[0]) in (numpy.bytes_, bytes):
                retStr += substr[0].decode('utf-8')
            else:
                retStr += substr[0]
        return(retStr)
    
    
    def getHeaderText(self):
        """getHeaderText returns the header record text as a string
        """
        if not 'Experiment Notes' in list(self._fi['Metadata'].keys()):
            return('')
        notes = self._fi['Metadata']['Experiment Notes']
        retStr = ''
        headerFound = False
        for substr in notes:
            if type(substr[0]) in (numpy.bytes_, bytes):
                if substr[0].find(b'Header information') != -1:
                    headerFound = True
            else:
                if substr[0].find('Header information') != -1:
                    headerFound = True
            if headerFound:
                if type(substr[0]) in (numpy.bytes_, bytes):
                    retStr += substr[0].decode('utf-8')
                else:
                    retStr += substr[0]
        return(retStr)
    
    
    def _getParmIndexDict(self):
        """_getParmIndexDict returns a dictionary with key = timestamps and ind spatial parm names,
            value = dictionary of keys = unique values, value = index of that value
        """
        retDict = {}
        parmList = ['ut1_unix'] + [parm[0].lower() for parm in self._fi['Metadata']['Independent Spatial Parameters']]
        for parm in parmList:
            if type(parm) in (numpy.bytes_, bytes):
                parm = parm.decode('utf-8')
            values = self._fi['Data']['Table Layout'][parm]
            unique_values = numpy.unique(values)
            sorted_values = numpy.sort(unique_values)
            retDict[parm] = collections.OrderedDict()
            for value, key in numpy.ndenumerate(sorted_values):
                if type(key) in (numpy.bytes_, bytes):
                    key = key.decode('utf-8')
                retDict[parm][key] = value[0]
        return(retDict)
            
        
    
    
    
class convertToText:
    def __init__(self, inputHdf5, outputTxt, summary='plain', showHeaders=False,
                  filterList=None, missing=None, assumed=None, knownbad=None):
        """convertToText converts a Madrigal HDF5 file to a text file. Designed to be able
        to handle large files without a large memory footprint
            
            Inputs:
                inputHdf5 - filename of input Madrigal Hdf5 file
                outputTxt - output text file
                summary - type of summary line to print at top.  Allowed values are:
                    'plain' - text only mnemonic names, but only if not showHeaders
                    'html' - mnemonic names wrapped in standard javascript code to allow descriptive popups
                    'summary' - print overview of file and filters used. Also text only mnemonic names, 
                        but only if not showHeaders
                    None - no summary line
                    
                showHeaders - if True, print header in format for each record.  If False, the default,
                    do not.
                    
                filterList - a list of madrigal.derivation.MadrigalFilter objects to be described in the 
                    summary.  Default is None, in which case not described in summary.  Ignored if summary
                    is not 'summary'
                    
                missing, assumed, knownbad - how to print Cedar special values.  Default is None for
                    all, so that value printed in value in numpy table as per spec.
        """
        madCedarObj = madrigal.cedar.MadrigalCedarFile(inputHdf5, maxRecords=10)
        madCedarObj.writeText(outputTxt, summary=summary, showHeaders=showHeaders, filterList=filterList,
                              missing=missing, assumed=assumed, knownbad=knownbad, append=True, 
                              firstWrite=True)
        while (True):
            newRecs, isComplete = madCedarObj.loadNextRecords(10)
            if newRecs == 0:
                break
            madCedarObj.writeText(outputTxt, summary=summary, showHeaders=showHeaders,
                                  missing=missing, assumed=assumed, knownbad=knownbad, 
                                  append=True, firstWrite=False)
            if isComplete:
                break
            if newRecs < 10:
                break
            
            
            
class mergeCedarFiles:
    def __init__(self, input1Hdf5, input2Hdf5, outputHdf5, includeDuplicate=False, skipArray=False):
        """mergeCedarFiles creates a new CEDAR Madrigal File by combining two CEDAR Madrigal input files.
        Records are merged in time.  Both files must have the same parameters.  Header and Catalog text from the
        first of the two files.
            
            Inputs:
                input1Hdf5 - filename of first input Madrigal Hdf5 file (header and catalog used for output file)
                input2Hdf5 - filename of second input Madrigal Hdf5 file (header and catalog ignored)
                outputHdf5 - output combined Hdf5 file, records sorted in time
                includeDuplicate - if False (the default), print message when two records have duplicate start and end
                    times and ignore one in input2Hdf5.  If True, include both (first input1Hdf5, then input2Hdf5)
                skipArray - if False and any 2D parms, create array layout (the default).  If True, skip array
                    layout (typically used when there are too many ind parm value combinations).
                    
        Reduces memory footprint using dump
        """
        input1 = madrigal.cedar.MadrigalCedarFile(input1Hdf5, maxRecords=10)
        arraySplitParms = input1.getArraySplitParms()
        if arraySplitParms == []:
            arraySplitParms = None
        input2 = madrigal.cedar.MadrigalCedarFile(input2Hdf5, maxRecords=10)
        output = madrigal.cedar.MadrigalCedarFile(outputHdf5, createFlag=True, arraySplitParms=arraySplitParms,
                                                  skipArray=skipArray)
        
        rec1 = 0 # index into input1
        rec2 = 0 # index into input2
        complete1 = False
        complete2 = False
        outputCount = 0  # used for
        
        while(True):
            # see if we need to dump output
            if outputCount > 0 and outputCount % 10 == 0:
                output.dump()
                
            # see if we need to load any more data
            
            if rec1 >= len(input1) and not complete1:
                # try to load more
                loaded, complete1 = input1.loadNextRecords(10)
                rec1 = 0
                    
            if rec2 >= len(input2) and not complete2:
                # try to load more
                loaded, complete2 = input2.loadNextRecords(10)
                rec2 = 0
                    
            if complete1 and complete2:
                # no more data
                break
            
            if not complete1:
                if input1[rec1].getType() != 'data':
                    # add catalog or header record
                    output.append(input1[rec1])
                    outputCount += 1
                    rec1 += 1
                    continue
            
            if not complete2:
                if input2[rec2].getType() != 'data':
                    # ignore catalog or header record
                    rec2 += 1
                    continue
            
            # add from remaining file if only one file left
            if complete1:
                output.append(input2[rec2])
                outputCount += 1
                rec2 += 1
                continue
            
            if complete2:
                output.append(input1[rec1])
                outputCount += 1
                rec1 += 1
                continue
            
            # now we know we have two data records - add earlier
            sDT1 = input1[rec1].getStartDatetime()
            sDT2 = input2[rec2].getStartDatetime()
            eDT1 = input1[rec1].getEndDatetime()
            eDT2 = input2[rec2].getEndDatetime()
            
            if sDT1 < sDT2:
                output.append(input1[rec1])
                outputCount += 1
                rec1 += 1
                continue
            
            elif sDT1 > sDT2:
                output.append(input2[rec2])
                outputCount += 1
                rec2 += 1
                continue
            
            elif eDT1 < eDT2:
                output.append(input1[rec1])
                outputCount += 1
                rec1 += 1
                continue
            
            elif eDT1 > eDT2:
                output.append(input2[rec2])
                outputCount += 1
                rec2 += 1
                continue
            
            # times match - handle depending on includeDuplicate
            if not includeDuplicate:
                # only take from first, throw away second
                output.append(input1[rec1])
                outputCount += 1
                rec1 += 1
                rec2 += 1
                print('Ignoring record from %s with duplicate times %s - %s' % (input2Hdf5,
                                                                                str(sDT2), str(eDT2)))
                continue
            
            else:
                # add both
                output.append(input1[rec1])
                output.append(input2[rec2])
                rec1 += 1
                rec2 += 1
                outputCount += 1 # not technically correct, but makes sure dump is not missed
                
        if outputCount % 10 != 0:
            output.dump()
            
        output.close()
                
            
    
    
class _TableSubset:
    """_TableSubset is a private class which defines a subset of a Table Layout created by
    one combination of array splitting parameter values
    """
    def __init__(self, arraySplittingParms,
                 arraySplittingValues,
                 fullTable):
        """TableSubset creates a TableSubset based on input parameters
        
        Inputs:
            arraySplittingParms - ordered list of mnemonics used to split table
            
            arraySplittingValues - values used for this subset
            
            fullTable - the full table to take a subset of
            
        Creates attributes:
            self.arraySplittingParms - input parm
            self.arraySplittingValues - input parm
            self.table - table subset
            self.oneDIndices - a numpy int array of indicies of one D values (one index per time/record)
        """
        self.arraySplittingValues = arraySplittingValues
        self.arraySplittingParms = []
        for parm in arraySplittingParms:
            if type(parm) in (numpy.bytes_, bytes):
                self.arraySplittingParms.append(parm.decode('utf8'))
            else:
                self.arraySplittingParms.append(parm)
        if len(self.arraySplittingParms) != len(self.arraySplittingValues):
            raise ValueError('Two input list must have equal length, not %i and %i' % \
                (len(self.arraySplittingParms), len(self.arraySplittingValues)))
        if len(self.arraySplittingParms) == 0:
            self.table = fullTable
            # get oneDIndices
            a1 = numpy.concatenate(([-1], self.table['recno']))
            a2 = numpy.concatenate((self.table['recno'], [-1]))
            self.oneDIndices = numpy.where(a1 != a2)
            self.oneDIndices = self.oneDIndices[0][:-1]
            return
        
        indices = None
        trueArr = numpy.ones((len(fullTable),), dtype=bool)
        falseArr = numpy.zeros((len(fullTable),), dtype=bool)
        if len(self.arraySplittingParms) == 1:
            indices = numpy.where(fullTable[arraySplittingParms[0]]==arraySplittingValues[0],
                                  trueArr, falseArr)
            self.table = fullTable[indices]
        
        # I can only figure out how to get numpy to AND two conditions at once, so do this as a loop
        else:
            for i in range(len(self.arraySplittingParms) - 1):
                if indices is None:
                    indices = numpy.where(numpy.logical_and(fullTable[self.arraySplittingParms[i]]==arraySplittingValues[i], 
                                                            fullTable[self.arraySplittingParms[i+1]]==arraySplittingValues[i+1]),
                                          trueArr, falseArr)
                else:
                    indices = numpy.where(numpy.logical_and(indices, 
                                                            fullTable[self.arraySplittingParms[i+1]]==arraySplittingValues[i+1]),
                                          trueArr, falseArr)
            self.table = fullTable[indices]
            
        # get oneDIndices
        a1 = numpy.concatenate(([-1], self.table['recno']))
        a2 = numpy.concatenate((self.table['recno'], [-1]))
        self.oneDIndices = numpy.where(a1 != a2)
        self.oneDIndices = self.oneDIndices[0][:-1]
        # verify the number of records == number of times
        if len(numpy.unique(self.table['ut1_unix'])) != len(self.oneDIndices):
            raise ValueError('Number of times %i not equal to number of records %i' % (len(numpy.unique(self.table['ut1_unix'])), len(self.oneDIndices)))
        
            
    def getGroupName(self):
        """getGroupName returns the group name in the form <Array with parm=value [and ...]>
        
        If no arraySplittingParms, returns None
        """
        arraySplittingParms = []
        for parm in self.arraySplittingParms:
            if type(parm) != str:
                arraySplittingParms.append(parm.decode('utf8'))
            else:
                arraySplittingParms.append(parm)
        if len(arraySplittingParms) == 0:
            return(None)
        groupName = 'Array with '
        for i, parm in enumerate(arraySplittingParms):
            groupName += '%s=%s ' % (parm, str(self.arraySplittingValues[i]))
            if i < len(self.arraySplittingValues)-1:
                groupName += 'and '
        return(groupName)


def compareParms(parm):
        """compareParms is used internally by getHeaderKodLines to order the parameters

        Inputs:

            parm - tuple of (code, parameter description, units) 


        Returns float(absolute value of code) + 0.5 if less than zero.  Else returns float(code)
            which results in positive code coming before negative of same absolute value
        """
        if parm[0] < 0:
            return(float(abs(parm[0])) + 0.5)
        else:
            return(float(abs(parm[0])))
    
    

        
if __name__ == '__main__':

    cedarObj = MadrigalCedarFile('/home/grail/brideout/madroot/experiments/1998/mlh/20jan98/mlh980120g.001')

    print('len of cedarObj is %i' % (len(cedarObj)))

    for i in range(2):
        print(cedarObj[i])
    
    cedarObj.write('Madrigal', '/home/grail/brideout/junk.001')

    newCedarObj = MadrigalCedarFile('/home/grail/brideout/madroot/experiments/1998/mlh/20jan98/mlh980120g.002', True)

    dataObj = MadrigalDataRecord(31,
                 1000,
                 2001,1,1,0,0,0,0,
                 2001,1,1,0,2,59,99,
                 ['azm', 'elm', 'rgate'],
                 ['range', 'ti', 'drange'],
                 4)

    dataObj.set1D('azm',45.0)
    dataObj.set1D('elm',85.0)
    dataObj.set2D(-120,2,'assumed')

    newCedarObj.append(dataObj)
    
    print(len(newCedarObj))

    print(newCedarObj)

    print(dataObj.get1D('azm'))
    print(dataObj.get1D('elm'))
    print(dataObj.get1D('rgate'))

    print(dataObj.get2D('range', 2))
    print(dataObj.get2D('drange', 2))

    dataObj.set2D('range', 0, 100)
    dataObj.set2D('range', 1, 150)
    dataObj.set2D('range', 2, 200)
    dataObj.set2D('range', 3, 250)

    print('kinst is %i' % (dataObj.getKinst()))
    print('kindat is %i' % (dataObj.getKindat()))

    oneDList = dataObj.get1DParms()
    print('The following are 1D parms:')
    for parm in oneDList:
        print(parm)

    print('now removing 1d rgate')
    dataObj.delete1D('rgate')

    oneDList = dataObj.get1DParms()
    print('The following are now the 1D parms:')
    for parm in oneDList:
        print(parm)

    twoDList = dataObj.get2DParms()
    print('\nThe following are 2D parms:')
    for parm in twoDList:
        print(parm)

    print(dataObj)

    print('now deleting drange')
    dataObj.delete2DParm('drange')

    print(dataObj)

    print('now deleting 2nd and 3rd row')
    dataObj.delete2DRows((1,2))

    print(dataObj)
