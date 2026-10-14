'''
views for docs app
 
@author: Bill Rideout
@contact: brideout@haystack.mit.edu

$Id: views.py 7738 2024-11-26 16:50:32Z brideout $
'''
# standard python imports
import os, os.path, sys
import random
import datetime
import mimetypes
import re
import xml.dom.minidom
import hashlib

# django imports
import django, django.http
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from . import forms
from wsgiref.util import FileWrapper

# madrigal imports
import madrigal.metadata
import madrigal.ui.web
import madrigal.openmadrigal
import subversion_operations
import github_operations

# note that github now holds Madrigal metadata, and subversion the experiment control files

# helper methods
def get_exp_info(control_file, rev):
    """get_exp_info returns a tuple of (exp_desc, cyc_desc, control_file_text) for the input control_file and revision.
    
    For now grabs info from Subversion on apollo
    """
    exp_desc = ''
    cyc_desc = ''
    control_file_text = ''
    
    subObj = subversion_operations.reader()
    xmlFilename  = control_file.replace('.dat', '.xml')
    output = os.path.join('/tmp', control_file)
    sub_path = 'millstone_geospace_radar/control/ISRExperiments'
    
    try:
        subObj.getFile(os.path.join(sub_path, control_file), '/tmp', rev)
    except:
        try:
            subObj.getFile(os.path.join(sub_path, control_file), '/tmp')
        except:
            return((exp_desc, cyc_desc, control_file_text))
        
    f = open(output)
    control_file_text = f.read()
    f.close()
    
    try:
        subObj.getFile(os.path.join(sub_path, xmlFilename), '/tmp', rev)
    except:
        try:
            subObj.getFile(os.path.join(sub_path, xmlFilename), '/tmp')
        except:
            return((exp_desc, cyc_desc, control_file_text))
        
    f = open(output)
    xml_file_text = f.read()
    f.close()
    
    
    
    # now build complete xml file
    cvsText = '<?xml version="1.0"?>\n<ExperimentDescriptionFile>\n'
    cvsText += xml_file_text

    # closing tag
    cvsText += '</ExperimentDescriptionFile>'


    expDescDoc = xml.dom.minidom.parseString(cvsText)


    # get all experiments
    expElemList = expDescDoc.getElementsByTagName("Experiment")
    
    for exp in expElemList:
        
        # get one exp name from exp list
        nameEl = exp.getElementsByTagName("ExperimentName")[0]

        # get text node, convert from unicode to ascii
        expName = ''
        for elem in nameEl.childNodes:
            if elem.nodeType == elem.TEXT_NODE:
               expName += elem.data.encode('utf-8')

        # get exp descriptions from exp list
        expDescElList = exp.getElementsByTagName("ExperimentDescription")

        for expDescEl in expDescElList:

            # get text node, convert from unicode to ascii
            expDesc = ''
            for elem in expDescEl.childNodes:
                if elem.nodeType == elem.TEXT_NODE:
                   expDesc += elem.data.encode('utf-8')
            if len(exp_desc) == 0:
                exp_desc = expDesc # make sure we get something even if no id match

            # get one CVS_rev
            cvsEl = expDescEl.getElementsByTagName("CVS_rev")[0]

            cvs = ''
            for elem in cvsEl.childNodes:
                if elem.nodeType == elem.TEXT_NODE:
                   cvs += elem.data.encode('utf-8')

            if cvs == rev:
                # right rev - overwrite
                if len(expDesc) == 0:
                    exp_desc = expDesc
                

            

        # get cycle descriptions from exp list
        cycDescElList = exp.getElementsByTagName("CycleDescription")

        for cycDescEl in cycDescElList:

            # get text node, convert from unicode to ascii
            cycDesc = ''
            for elem in cycDescEl.childNodes:
                if elem.nodeType == elem.TEXT_NODE:
                   cycDesc += elem.data.encode('utf-8')
                   
            if len(cyc_desc) == 0:
                cyc_desc = cycDesc # make sure we get something even if no id match

            # get one CVS_rev
            cvsEl = cycDescEl.getElementsByTagName("CVS_rev")[0]

            cvs = ''
            for elem in cvsEl.childNodes:
                if elem.nodeType == elem.TEXT_NODE:
                   cvs += elem.data.encode('utf-8')

            if cvs == rev:
                # right rev - overwrite
                if len(cycDesc) == 0:
                    cyc_desc = cycDesc

        
    return((exp_desc, cyc_desc, control_file_text))
    
    

@csrf_exempt
def get_log_admin(request):
    """get_log_admin returns the admin access log page.  
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    
    if request.method == 'POST':
        form = forms.AdminLogForm(request.POST, request=request)
        if form.is_valid():
            
            cleaned_data = form.cleaned_data
            kinstList = [int(item) for item in eval(cleaned_data['kinst'])]
            startDT = datetime.datetime(cleaned_data['startDate'].year, cleaned_data['startDate'].month, cleaned_data['startDate'].day)
            endDT = datetime.datetime(cleaned_data['endDate'].year, cleaned_data['endDate'].month, cleaned_data['endDate'].day)
            madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
            stageDir = os.path.join(madDB.getMadroot(), 'experiments/stage')
            tmpFile = os.path.join(stageDir, 'admin_%i.log' % (random.randint(0, 1000000)))
            madWebObj.filterLog(tmpFile, kinstList, startDT, endDT)
            f = open(tmpFile, 'r')
            thisFile = django.core.files.File(f)
            response = django.http.HttpResponse(thisFile, content_type='application/x-octet-stream')
            response['Content-Disposition'] = 'attachment; filename="' + os.path.basename(tmpFile) + '"'
            response['Content-Length'] = os.path.getsize(tmpFile)
            response.set_cookie('fileDownload', 'true', path='/', samesite='Strict')
            return(response)

    else:
        form = forms.AdminLogForm(request=request)
    
    responseDict = {'bg_color': bg_color}
    responseDict['form'] = form
    return render(request, 'get_log_admin.html', responseDict)


def get_latest_metadata_version(request):
    """get_latest_metadata_version returns the latest version of the specified metadata file
    
    Inputs:
        request - contains key fullPath - full path to the Madrigal file in Subversion relative to trunk
            (example: 'madroot/metadata/siteTab.txt')
    """
    fullPath = request.GET['fullPath']
    
    subObj = github_operations.reader()
    output = os.path.join('/tmp', os.path.basename(fullPath))
    subObj.getFile(fullPath, '/tmp')
    
    f = open(output)
    fileStr = f.read()
    f.close()
    try:
        os.remove(output)
    except:
        pass
    
    return(django.http.HttpResponse(fileStr))


def get_all_metadata_versions(request):
    """get_all_metadata_versions returns the a page listing all versions numbers available for a given metadata
    file, one line for each version string
    
    Inputs:
        request - contains key fullPath - full path to the Madrigal file in Subversion relative to trunk
            (example: 'madroot/metadata/siteTab.txt')
            
    """
    fullPath = request.GET['fullPath']
    
    subObj = github_operations.reader()
    revDict = subObj.getFileRevsDates(fullPath)
            
    retStr = ''
    for k in sorted(revDict):
        retStr += '{}\n'.format(revDict[k])
    
    return(django.http.HttpResponse(retStr))


def get_metadata_version(request):
    """get_metadata_version returns the specifed version of the specified metadata file
    
    Inputs:
        request - contains key fullPath - full path to the Madrigal file in Subversion relative to trunk
            (example: 'madroot/metadata/siteTab.txt'), and key version
        
    """
    fullPath = request.GET['fullPath']
    version = request.GET['version']
    
    subObj = github_operations.reader()
    output = os.path.join('/tmp', os.path.basename(fullPath))
    subObj.getFile(fullPath, '/tmp', version)
    
    f = open(output, 'rb')
    text = f.read()
    f.close()
    try:
        os.remove(output)
    except:
        pass
    
    return(django.http.HttpResponse(text))


def get_open_madrigal_shared_files(request):
    """get_open_madrigal_shared_files returns the specifed version of the shared OpenMadrigal file 
    
    Inputs:
        request - contains key filename - in form siteName_siteID/expTab.txt or siteName_siteID/fileTab.txt
        
    For now hardcoded path to files
    """
    path = '/opt/openmadrigal/madroot/source/madpy/djangoMad/madweb/static/distributionFiles/metadata' # used because siteTab.txt for mad3 is incompatible
    filename = request.GET['filename']

    validFnames = ["siteTab.txt", "instTab.txt",
                    "instType.txt", "status.dat",
                    "ig_rz.dat", "expTab.txt",
                    "fileTab.txt", "geofil.tar.gz"]

    # validate filename
    if ".." in filename:
        # directory traversal is not allowed
        return(django.http.HttpResponse("Directory traversal not allowed"))
    
    fsplit = filename.split("/")
    if len(fsplit) > 2:
        # contains extra dir, not allowed
        return(django.http.HttpResponse("Invalid dirname {}".format(filename)))
    
    if (len(fsplit) == 2) and ("mad3" in filename):
        filename = fsplit[1]
    
    elif (len(fsplit) == 2) and (len(fsplit[0].split("_")) != 2):
        # invalid site directory
        return(django.http.HttpResponse("Invalid site dir {}".format(filename)))
    
    valid = False
    for fname in validFnames:
        if fname in filename:
            valid = True

    if not valid:
        return(django.http.HttpResponse("Invalid filename {}".format(filename)))

    fullPath = os.path.join(path, filename)

    if fullPath.endswith(".tar.gz"):
        f = open(fullPath, "rb")
        chunk_size = 8192
        file_type = mimetypes.guess_type(fullPath)[0]
        if file_type is None:
            file_type = 'application/octet-stream'
        response = django.http.StreamingHttpResponse(FileWrapper(f, chunk_size),
                                        content_type=file_type)
        response['Content-Length'] = os.path.getsize(fullPath)    
        response['Content-Disposition'] = "attachment; filename=%s" % (filename)
        return(response)
    else:
        f = open(fullPath, 'r')
        text = f.read()
        f.close()
        return(django.http.HttpResponse(text))
    
  
def get_madrigal_videos(request):
    """get_madrigal_videos returns the Madrigal video tutorials page 
    
    Inputs:
        request 
        
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    responseDict = {'bg_color': bg_color}
    return render(request, 'get_video_tutorials.html', responseDict)

def get_exp_notes(request):
    """get_exp_notes returns the description of the control file - links from catalog in MLH files
    
    Inputs:
        request 
        
    """
    responseDict = {}
    responseDict['control_file'] = request.GET['exp']
    responseDict['rev'] = request.GET['rev']
    
    exp_desc, cyc_desc, control_file_text = get_exp_info(responseDict['control_file'],
                                                         responseDict['rev'])
    
    responseDict['exp_desc'] = exp_desc
    responseDict['cyc_desc'] = cyc_desc
    responseDict['control_file_text'] = control_file_text
    
    
    return render(request, 'exp_notes.html', responseDict)


def compare_to_archive(request):
    """compare_to_archive implements the old compareToArchive.py cgi script
    
    Now checks newest to oldest, up to 50 max
    """
    filePath = request.GET['filePath']
    fileTextMd5 = request.GET['fileTextMd5']
    strip = False
    if 'strip' in request.GET:
        strip = True
    madDB = madrigal.metadata.MadrigalDB()
    openMadObj = madrigal.openmadrigal.OpenMadrigal(madDB)
    revList = openMadObj.getAllRevisionNumbers(filePath)
    revList.reverse() # check newest first

    if len(revList) == 0:
        return(django.http.HttpResponse('None None'))
    
    # loop through all revisions, looking for a match
    for rev in revList[:50]:
        thisText = openMadObj.getCvsVersion(filePath, rev)
        if thisText is None:
            continue
        if strip:
            data = thisText.strip().encode()
            thisMd5 = hashlib.md5(data)
        else:
            thisMd5 = hashlib.md5(thisText.encode())
        if thisMd5.hexdigest() == fileTextMd5:
            return(django.http.HttpResponse('%s %s' % (revList[0], rev)))

    # no matches found
    return(django.http.HttpResponse('%s None' % (revList[0])))
 

def open_madrigal(request):
    """openmadrigal implements the openmadigal page
    """
    madDB = madrigal.metadata.MadrigalDB()
    madSiteObj = madrigal.metadata.MadrigalSite(madDB)
    responseDict = {}
    site_list = []
    for siteId, siteName in madSiteObj.getSiteList():
        if madSiteObj.getSiteServer(siteId).find('http') == -1:
            url = 'http://' + os.path.join(madSiteObj.getSiteServer(siteId),
                                           madSiteObj.getSiteDocRoot(siteId))
        else:
            url = os.path.join(madSiteObj.getSiteServer(siteId),
                               madSiteObj.getSiteDocRoot(siteId))
        site_list.append((url, siteName))
        
    responseDict['site_list'] = site_list
    return(render(request, 'openmadrigal.html', responseDict))

def madrigal_admin(request):
    """madrigal_admin implements the openmadigal admin page
    """
    responseDict = {}
    return(render(request, 'admin.html', responseDict))

def madrigal_download(request):
    """madrigal_download implements the openmadigal download page
    """
    responseDict = {}
    return(render(request, 'madDownload.html', responseDict))

def get_citation_group_service(request):
    """get_citation_group returns a list of citations created as a group using a group id
    """
    madDB = madrigal.metadata.MadrigalDB()
    id = int(request.GET['id'])
    citations = madDB.getListFromGroupId(id)
    
    text = ''
    for url in citations:
        text += '%s\n' % (url)
    
    return render(request, 'service.html', {'text': django.utils.safestring.mark_safe(text)})

def create_citation_group_with_list(request):
    """create_citation_group_with_list create a citation group through passed in group of citations.
    
    Returns citation to group
    """
    madDB = madrigal.metadata.MadrigalDB()
    try:
        user_fullname = request.GET['user_fullname']
    except KeyError:
        return render(request, 'service.html', {'text': 'user_fullname argument missing'})
    try:
        user_email = request.GET['user_email']
    except KeyError:
        return render(request, 'service.html', {'text': 'user_email argument missing'})
    try:
        user_affiliation = request.GET['user_affiliation']
    except KeyError:
        return render(request, 'service.html', {'text': 'user_affiliation argument missing'})
    citations=request.POST.getlist('url')[0]
    cmd = 'local_citations = %s' % (citations)
    ldict = {}
    exec(cmd, globals(), ldict)
    citations = ldict['local_citations']
    if len(citations) == 0:
        return render(request, 'service.html', {'text': 'url argument missing; multiple allowed'})
    # verify citations in proper format
    for citation in citations:
        if citation[:11] not in ('https://w3i', 'experiments'):
            return render(request, 'service.html', {'text': 'Illegal url %s' % (citation)})
    id = madDB.createGroupIdWithList(user_fullname, user_email, user_affiliation, citations)
    return render(request, 'service.html', {'text': 'https://cedar.openmadrigal.org/getCitationGroup?id=%i\n' % (id)})
    
    
def get_citation_group_with_filters(request):
    """get_citation_group_with_filters returns a list of citations (one per line) using filters similar to globalDownload.
    Result can then be used to create citation group using create_citation_group_with_list 
    
    Request contains to following keys:
            startDate: start datetime to filter experiments before in YYYY-MM-DD (required)
            endDate: end datetime to filter experiments after  in YYYY-MM-DD (required)
            inst: a list of instrument codes or names. If not set, all instruments used. 
                For names fnmatch will be used
            kindat: a list of kind of data codes or names. If not set, all kindats used. 
                For names fnmatch will be used
            seasonalStartDate: in form MM/DD, rejects all days earlier in year. If not set,
                implies 01/01
            seasonalEndDate: in form MM/DD, rejects all days later in year. If not set,
                implies 12/31
            includeNonDefault: if set, include realtime files when there are no default. If not set,
                implies only default files.
            expName: string - filter experiments by the experiment name.  fnmatch rules
                If not set, no filtering by experiment name.
            excludeExpName: string - exclude experiments by the experiment name.  fnmatch rules  
                If not set, no excluding experiments by experiment name.
            fileDesc: filter files using input file Description string via fnmatch. 
                If not set, no filtering by file name
            dateList: comma separated list of date strings in the form YYYY-MM-DD, to get experiments for \
                a list of discrete days. Must include startDate and endDate.
    
    Returns a list with all citations in group, one per line
    """
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    if not 'startDate' in request.GET:
        return(django.http.HttpResponse('<p>startDate required for getCitationGroupWithFilters</p>'))
    startDate = request.GET.get('startDate')
    startDate = datetime.datetime.strptime(startDate, '%Y-%m-%d')
    endDate = request.GET.get('endDate')
    endDate = datetime.datetime.strptime(endDate, '%Y-%m-%d')
    inst = request.GET.getlist('inst')
    if len(inst) == 0:
        inst = None
    kindat = request.GET.getlist('kindat')
    if len(kindat) == 0:
        kindat = None
    seasonalStartDate = request.GET.get('seasonalStartDate')
    seasonalEndDate = request.GET.get('seasonalEndDate')
    if 'includeNonDefault' in request.GET:
        includeNonDefault = True
    else:
        includeNonDefault = False
    expName = request.GET.get('expName')
    excludeExpName = request.GET.get('excludeExpName')
    fileDesc = request.GET.get('fileDesc')
    dateList = request.GET.getlist('dateList')
    if len(dateList) == 0:
        dateList = None
    else:
        dateList = [datetime.datetime.strptime(item, '%Y-%m-%d%z').date() for item in dateList]
    citations = madWebObj.global_file_search(startDate, endDate, inst, kindat, 
                           seasonalStartDate, seasonalEndDate, 
                           includeNonDefault, expName, excludeExpName, 
                           fileDesc, returnCitation=True, dateList=dateList)
    if len(citations) == 0:
        return render(request, 'service.html', {'text': 'No citations found with given filters - no group citation created'})
    else:
        text = ''
    for url in citations:
        text += '%s\n' % (url)
    return render(request, 'service.html', {'text': text})
    
    
