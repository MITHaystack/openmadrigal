#!PYTHONEXE

"""This script is the old version of isprint that worked with Madrigal 2.X Cedar format files.  It exists only to help
the conversion process from Madrigal 2.X to Madrigal 3.0.

Deprecated notes:

This script replaces the command line version of the isprint Fortran application.  It is based on the maddata
engine as found in madc/madrec, and exposed to python via _Madrec.c.

It is different from the old isprint application in the following ways:
1.  It works with any legal Cedar file format, not just the Madrigal format.
2.  It allows any parameter to be used in filters, not just the few offered by the Fortran isprint application

It is similar in that it supports most of the options that the Fortran isprint application did

$Id: isprint_deprecated.py 7046 2019-10-07 19:57:14Z brideout $
"""

import sys
import os
import traceback


usageStr = """Usage: isprint_deprecated.py file=<path to old format Cedar file>
     date1=<mm/dd/yyyy - starting date to be examined - defaults to first day>
     time1=<hh:mm:ss - starting UT time to be examined - defaults to 0>
     date2=<mm/dd/yyyy - ending date to be examined - defaults to last day>
     time2=<hh:mm:ss - ending UT time to be examined - defaults to 24>
     (in the follow arguments, any value missing may be used to indicate no lower or upper limit)
     z=<lower alt limit1>,<upper alt limit1>[or<lower alt limit2>,<upper alt limit2>...] (km)
     az=<lower az limit1>,<upper az limit1>[or<lower az limit2>,<upper az limit2>...] (from -180 to 180)
     el=<lower el limit1>,<upper el limit1>[or<lower el limit2>,<upper el limit2>...] (from 0 to 90)
     plen=<lower pl limit1>,<upper pl limit1>[or<lower pl limit2>,<upper pl limit2>...] (pulse len in sec)
     header=<t or f> (defaults to header=t, show headers)
     summary=<t or f> (defaults to summary=t, show summary)
     badval=<bad value string> (defaults to "missing")
     assumed=<assumed value string> (defaults to "assumed")
     knownbad=<known bad value string> (defaults to "knownbad")
     mxchar=<maximum characters per line> (minimum 50 - defaults to no maximum)
     filter=<[mnemonic] or [mnemonic1,[+-*/]mnemonic2]>,<lower limit1>,<upper limit1>[or<lower limit2>,<upper limit2>...]
        (any number of filters may be added)
     <list of mnemonics to display> (will be show in order listed)

Example:

    isprint_deprecated.py file=/opt/madrigal/experiments/1998/mlh/20jan98/mil980120g.003 date1=01/20/1998
    time1=15:00:00 date2=01/20/1998 time2=16:00:00 z=200,300or500,600 badval=noData
    filter=gdalt,-,sdwht,0, filter=ti,500,1000 uth gdalt gdlat glon ti te

This example would show data from mil980120g.003 between 15 and 16 UT on 01/20/1998 where
altitude is either between 200 and 300 km or between 500 and 600 km, and where gdalt-sdwht is
greater than 0 (point is in sunlight), and where ti is between 500 and 1000.  "noData" would
be printed if data was not available.

See complete instructions at http://www.haystack.mit.edu/madrigal/isprint.html
"""

def appendFilter(filter, type, parm1, parm2, numRanges, lowRangeList, highRangeList):
    """ appendFilter adds to the lists that make up a filter, which is a list of lists.

    Inputs:
        filter - the existing list of 6 lists to be appended to
        type - '1','*','/','+', or '-'.  If '1', parm2 not needed
        parm1 - filter mnemonic 1
        parm2 - filter mnemonic 1 - may be None if type = 1
        numRanges - number of ranges to add for this filter
        lowRangeList - list of lower limits; len must = numRanges
        highRangeList - list of upper limits; len must = numRanges

    Outputs: None

    Affects:  Appends to the following 6 lists in the filter:

        filtTypeList:    filter types, len = # filters, chars are '1','*','/','+', or '-'
        filtParm1List:   mnemonics of filter parameter 1 (items = # filters)
        filtParm2List:   mnemonics of filter parameter 2 (items = # filters) (may be None)
        filtNumRangeList: number of ranges per filter (items = # filters)
        filterLowList:   doubles of filter lower limits (items = sum of number of ranges above)
        filterHighList:  doubles of filter upper limits (items = sum of number of ranges above) 
    """
    # type
    if type not in ['1', '+', '-', '*', '/']:
        raise IOError("Illegal type: " + str(type))
    filter[0].append(type)

    #parm1
    filter[1].append(parm1)

    #parm2
    if type != '1':
        filter[2].append(parm2)
    else:
        filter[2].append(None)

    # numRanges
    filter[3].append(numRanges)

    #lowRangeList
    if len(lowRangeList) != numRanges:
        raise IOError("Wrong number of items in lowRangeList: " + str(numRanges) + ' ' + str(lowRangeList))
    for item in lowRangeList:
        if len(item) != 0:
            filter[4].append(float(item))
        else:
            filter[4].append(None)

    #highRangeList
    if len(highRangeList) != numRanges:
        raise IOError("Wrong number of items in highRangeList")
    for item in highRangeList:
        if len(item) != 0:
            filter[5].append(float(item))
        else:
            filter[5].append(None)
    
    
#  ********* main script begins here ***************
# catch any exception, and write an appropriate message
try:

    # check if pythonlibpath env variable exists
    # written 'PYTHON' + 'LIBPATH' to stop automatic replacement during setup
    temp = os.environ.get('PYTHON' + 'LIBPATH')
    if temp != None:
            sys.path.append(temp)
            
    # append path madroot/lib (needed only if python not installed by setup)
    sys.path.append('MADROOT/lib/python')

    # prepare to handle MadrigalError
    import madrigal.admin
    
except ImportError:
    
    # Fatal error - madpy library not found
    print("Unable to import the madrigal python library - please alert the sys admin!")
    sys.exit(0)

# try to run script, and report all errors to Madrigal sys admin

try:

    import madrigal.metadata
    import madrigal.data
    import madrigal._Madrec

    # create MadrigalDB obj
    madDBObj = madrigal.metadata.MadrigalDB()

    # create MadrigalParm obj
    madParmObj = madrigal.data._DeprecatedMadrigalParameters(madDBObj)

    # create an empty filter
    filter = [[],[],[],[],[],[]]

    # inital values
    desiredParmList = []
    filename = ''
    header = 1
    summary = 1
    badvalStr = 'missing'
    assumedStr = 'assumed'
    knownbadStr = 'knownbad'
    mxchar = 10000
    date1 = ''
    time1 = ''
    date2 = ''
    time2 = ''



    # parse arguments
    if len(sys.argv) == 1:
        print(usageStr)
        sys.exit(0)

    for arg in sys.argv[1:]:

        lowerLimList = []
        upperLimList = []
        
        # skip isprint command
        if arg.find('isprint_deprecated.py') != -1:
            continue
        
        # check if its a parameter
        if arg.find('=') == -1:
            if madParmObj.getParmType(arg) == -1:
                raise IOError("Illegal parameter: " + str(arg))
            desiredParmList.append(madParmObj.getParmMnemonic(arg))
            continue

        # check if its a file
        if arg.find('file=') != -1:
            filename = arg[arg.find('=')+1:]
            continue

        # check for header
        if arg[:7] == 'header=':
            if arg[7] in ['f', 'F']:
                header = 0
            elif arg[7] not in ['t', 'T']:
                raise IOError("Bad argument for header, must be t or f")
            continue

        # check for summary
        if arg[:8] == 'summary=':
            if arg[8] in ['f', 'F']:
                summary = 0
            elif arg[8] not in ['t', 'T']:
                raise IOError("Bad argument for summary, must be t or f")
            continue
                
        # check for badval
        if arg[:7] == 'badval=':
            badvalStr = arg[7:]
            continue

        # check for assumed
        if arg[:8] == 'assumed=':
            assumedStr = arg[8:]
            continue

        # check for knownbad
        if arg[:9] == 'knownbad=':
            knownbadStr = arg[9:]
            continue

        # check for mxchar
        if arg[:7] == 'mxchar=':
            try:
                mxchar = int(arg[7:])
                if mxchar < 50:
                    print("Lowest limit for mxchar is 50 - setting to 50")
                    mxchar = 50
            except:
                raise IOError("Illegal argument for mxchar: " + str(arg[7:]))
            continue
        

        # check if its date1
        if arg[:6] == 'date1=':
            date1 = arg[arg.find('=')+1:]
            continue

        # check if its time1
        if arg[:6] == 'time1=':
            time1 = arg[arg.find('=')+1:]
            continue

        # check if its date2
        if arg[:6] == 'date2=':
            date2 = arg[arg.find('=')+1:]
            continue

        # check if its time2
        if arg[:6] == 'time2=':
            time2 = arg[arg.find('=')+1:]
            continue

        # check if its z argument
        if arg[:2] == 'z=':
            argStr = arg[arg.find('=')+1:]
            # get number of ranges
            zRangeList = argStr.split('or')
            for zRange in zRangeList:
                limList = zRange.split(',')
                if len(limList) != 2:
                    raise IOError("Illegal range in z filter")
                lowerLimList.append(limList[0])
                upperLimList.append(limList[1])

            #append filter
            appendFilter(filter, '1', 'gdalt', '', len(zRangeList),
                         lowerLimList, upperLimList)
            continue
            
        # check if its az argument
        if arg[:3] == 'az=':
            argStr = arg[arg.find('=')+1:]
            # get number of ranges
            azList = argStr.split('or')
            for az in azList:
                limList = az.split(',')
                if len(limList) != 2:
                    raise IOError("Illegal range in az filter")
                lowerLimList.append(limList[0])
                upperLimList.append(limList[1])
                # check for valid az
                if float(limList[0]) < -180.0 or float(limList[0]) > 180.0:
                    raise IOError("Illegal az - must be -180 to 180: " + str(limList[0]))
                if float(limList[1]) < -180.0 or float(limList[1]) > 180.0:
                    raise IOError("Illegal az - must be -180 to 180: " + str(limList[1]))

            #append filter
            appendFilter(filter, '1', 'azm', '', len(azList),
                         lowerLimList, upperLimList)
            continue


        # check if its el argument
        if arg[:3] == 'el=':
            argStr = arg[arg.find('=')+1:]
            # get number of ranges
            elList = argStr.split('or')
            for el in elList:
                limList = el.split(',')
                if len(limList) != 2:
                    raise IOError("Illegal range in el filter")
                lowerLimList.append(limList[0])
                upperLimList.append(limList[1])
                # check for valid el
                if float(limList[0]) < 0.0 or float(limList[0]) > 90.0:
                    raise IOError("Illegal el - must be 0 to 90: " + str(limList[0]))
                if float(limList[1]) < 0.0 or float(limList[1]) > 90.0:
                    raise IOError("Illegal el - must be 0 to 90: " + str(limList[1]))

            #append filter
            appendFilter(filter, '1', 'elm', '', len(elList),
                         lowerLimList, upperLimList)
            continue

        # check if its plen argument
        if arg[:5] == 'plen=':
            argStr = arg[arg.find('=')+1:]
            # get number of ranges
            plList = argStr.split('or')
            for pl in plList:
                limList = pl.split(',')
                if len(limList) != 2:
                    raise IOError("Illegal range in pulse length filter")
                lowerLimList.append(limList[0])
                upperLimList.append(limList[1])

            #append filter
            appendFilter(filter, '1', 'pl', '', len(plList),
                         lowerLimList, upperLimList)
            continue

        # finally, check if its a filter argument
        if arg[:7] == 'filter=':
            argStr = arg[arg.find('=')+1:]
            #get mnemonic string
            itemList = argStr.split(',')
            if itemList[1] in ['+','-','*','/']:
                # two mnemonics used
                twoMnem = 1
                mnem1 = itemList[0]
                operator = itemList[1]
                mnem2 = itemList[2]
                # check that both are valid
                if madParmObj.getParmType(mnem1) == -1:
                    raise IOError("Illegal parameter: " + str(mnem1))
                if madParmObj.getParmType(mnem2) == -1:
                    raise IOError("Illegal parameter: " + str(mnem2))
            else:
                # one menmonic
                twoMnem = 0
                mnem1 = itemList[0]
                operator = '1'
                mnem2 = ''
                # check mnem1 is valid
                if madParmObj.getParmType(mnem1) == -1:
                    raise IOError("Illegal parameter: " + str(mnem1))

            
            # get ranges
            delimiter = ','
            rangeStr = delimiter.join(itemList[1 + 2*twoMnem:])
            rangeList = rangeStr.split('or')
            for thisRange in rangeList:
                limList = thisRange.split(',')
                if len(limList) != 2:
                    raise IOError("Illegal range in filter")
                lowerLimList.append(limList[0])
                upperLimList.append(limList[1])

            #append filter
            appendFilter(filter, operator, mnem1, mnem2, len(rangeList),
                         lowerLimList, upperLimList)
            continue

        # unknown argument
        print('Argument %s is unknown - see usage' % (arg))
        print('\n')
        print(usageStr)
        sys.exit(0)

    # command line fully parsed - finally set up the time filter based on
    # date, time args if needed

    if len(date1) or len(time1) or len(date2) or len(time2):
        # if time1 is given but not date1, set up a UTH filter
        if len(time1) and len(date1)==0:
            time1List = time1.split(':')
            if len(time1List) != 3:
                raise IOError("Illegal value for time1: " + time1)
            beg_uth = float(time1List[0])
            beg_uth += float(time1List[1])/60.0
            beg_uth += float(time1List[2])/3600.0
            appendFilter(filter, '1', 'UTH', '', 1,
                         [str(beg_uth)], [''])

        # if time2 is given but not date1 or date2, set up a UTH filter
        if len(time2) and len(date1)==0 and len(date2)==0:
            time2List = time2.split(':')
            if len(time2List) != 3:
                raise IOError("Illegal value for time2: " + time2)
            end_uth = float(time2List[0])
            end_uth += float(time2List[1])/60.0
            end_uth += float(time2List[2])/3600.0
            appendFilter(filter, '1', 'UTH', '', 1,
                         [''], [str(end_uth)])

        # set up UT1 filter if both date and times given
        beg_ut1 = ''
        end_ut1 = ''
        
        if (date1):
            if time1 == '':
                time1 = '00:00:00'
            time1List = time1.split(':')
            if len(time1List) != 3:
                raise IOError("Illegal value for time1: " + time1)
            date1List = date1.split('/')
            if len(date1List) != 3:
                raise IOError("Illegal value for date1: " + date1)
            beg_ut1 = madrigal._Madrec.getUtFromDate(int(date1List[2]),
                                                     int(date1List[0]),
                                                     int(date1List[1]),
                                                     int(time1List[0]),
                                                     int(time1List[1]),
                                                     int(time1List[2]),
                                                     0)
            beg_ut1 = str(beg_ut1)

            # now check for the case that time2 given, but not date2
            # in which case time2 referes to date1
            if len(time2) and len(date2)==0:
                end_ut1 = madrigal._Madrec.getUtFromDate(int(date1List[2]),
                                                         int(date1List[0]),
                                                         int(date1List[1]),
                                                         0,
                                                         0,
                                                         0,
                                                         0)
                time2List = time2.split(':')
                if len(time2List) != 3:
                    raise IOError("Illegal value for time2: " + time2)
                end_ut1 += float(time2List[0]) * 3600.0
                end_ut1 += float(time2List[1]) * 60.0
                end_ut1 += float(time2List[2])
                end_ut1 = str(end_ut1)
                

        if len(date2):
            if time2 == '':
                time2 = '00:00:00'
            time2List = time2.split(':')
            if len(time2List) != 3:
                raise IOError("Illegal value for time2: " + time2)
            date2List = date2.split('/')
            if len(date2List) != 3:
                raise IOError("Illegal value for date2: " + date2)
            end_ut1 = madrigal._Madrec.getUtFromDate(int(date2List[2]),
                                                     int(date2List[0]),
                                                     int(date2List[1]),
                                                     int(time2List[0]),
                                                     int(time2List[1]),
                                                     int(time2List[2]),
                                                     0)
            end_ut1 = str(end_ut1)

        # append ut1 filter if needed
        if len(beg_ut1) != 0 or len(end_ut1) != 0:
            appendFilter(filter, '1', 'UT1', '', 1,
                         [beg_ut1], [end_ut1])

    # check that filename was given
    if len(filename) == 0:
        raise IOError('Required argument file missing')


    madrigal._Madrec.getIsprintReport(filename,
                                      '',
                                      desiredParmList,
                                      filter[0],
                                      filter[1],
                                      filter[2],
                                      filter[3],
                                      filter[4],
                                      filter[5],
                                      header,
                                      summary,
                                      int(mxchar),
                                      badvalStr,
                                      assumedStr,
                                      knownbadStr,
                                      'stdout')

except:
    # handle an error

    # if a normal SystemExit, simply terminate
    if str(sys.exc_info()[0]).find('exceptions.SystemExit') != -1:
        sys.exit(0)

    if sys.exc_info()[0] != None:
        print('\n****  ' + str(sys.exc_info()[0]) + '  ****\n')
    if sys.exc_info()[1] != None:
        print('\n****  ' + str(sys.exc_info()[1]) + '  ****\n')
    if sys.exc_info()[0] == None and sys.exc_info()[1] == None:
        print()
        traceback.print_exc()


# end script


