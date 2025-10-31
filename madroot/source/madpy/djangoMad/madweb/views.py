'''

@author: Bill Rideout
@contact: brideout@haystack.mit.edu

$Id: views.py 7667 2024-07-30 19:28:29Z kcariglia $
'''
# standard python imports
import os.path
import urllib, urllib.parse
import os, sys
import json
import datetime, time
import glob
import re
import subprocess
import io
import collections
import shutil
import mimetypes
import tempfile
import random

# django imports
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect
from django.template.context import RequestContext
#from django.conf import settings
try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, StreamingHttpResponse
import django.core.files
import django.utils.safestring
from wsgiref.util import FileWrapper

# third party imports
import numpy


# madrigal imports
import madrigal._derive
import madrigal.metadata
import madrigal.ui.web
import madrigal.cedar
import madrigal.isprint
import madweb.forms


# temp only
import logging


# constants
formatDict = collections.OrderedDict()
formatDict['hdf5'] = 'Hdf5'
formatDict['netCDF4'] = 'netCDF4'
formatDict['ascii'] = 'Column-delimited ascii'
maxSize = 50000000 # 50 MB cutoff



@csrf_protect
def index(request):
    """index is the home page view
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    welcome = madDB.getIndexHead()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    rulesRoadHtml = madDB.getLocalRulesOfRoad()
    template_dict = {'home_active': 'class="active"', 'site_name': siteName, 'site_list': siteList,
                     'rulesOfRoad':django.utils.safestring.mark_safe(rulesRoadHtml),
                     'bg_color': bg_color, 'welcome': welcome}
    return render(request, 'madweb/index.html', template_dict)


@csrf_protect
def check_registration(request):
    # this checks if all the needed cookies are set
    try:
        cookieDict = request.COOKIES
        cookieDict['user_fullname']
        cookieDict['user_email']
        cookieDict['user_affiliation']
        # no need to register
        return(request)
    except:
        return(HttpResponseRedirect(reverse('view_registration') + '?redirect=%s' % (request.get_full_path())))
    
            
@csrf_protect        
def view_registration(request):
    madDB = madrigal.metadata.MadrigalDB()
    madWeb = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWeb.getSiteInfo()
    contactEmail = madDB.getContactEmail()
    redirect = 'index' # default is to redirect to home page
    if request.method == 'GET':
        if 'redirect' in request.GET:
            redirect = request.GET['redirect']
            for key in request.GET:
                if key not in ('redirect', 'user_fullname', 'user_email', 'user_affiliation'):
                    redirect += '&%s=%s' % (key, request.GET[key])
        if len(list(request.GET.keys())) > 0 and 'user_fullname' in request.GET:
            form = madweb.forms.RegisterForm(request.GET)
            if form.is_valid():
                # write cookies and continue to main page
                max_age = 3600*24*365 # one year
                if redirect == 'index':
                    response = HttpResponseRedirect(reverse('index'))
                else:
                    response = HttpResponseRedirect(redirect)
                response.set_cookie('user_fullname', form.cleaned_data['user_fullname'], max_age=max_age, samesite='lax')
                response.set_cookie('user_email', form.cleaned_data['user_email'], max_age=max_age, samesite='lax')
                response.set_cookie('user_affiliation', form.cleaned_data['user_affiliation'], max_age=max_age, samesite='lax')
                return(response)
        else:
            form = madweb.forms.RegisterForm()
            
    else:
       form = madweb.forms.RegisterForm()
       
    return render(request, 'madweb/register.html', {'form': form, 'home_active': 'class="active"',
                                                   'site_name': siteName, 'site_list': siteList,
                                                   'contact_email': contactEmail, 'redirect': redirect})
    
            

    

@csrf_protect
def view_single(request):
    """view_single is the single experiment view.  It is supplemented by ajax views to speed performamnce,
    but this view can also create the entire page given a complete query string
    """
    request = check_registration(request)

    if type(request) == HttpResponseRedirect:
        return(request)

    responseDict = {'single_active': 'class="active"'}
    cookieDict = request.COOKIES
    user_email = cookieDict['user_email']
    queryDict = request.GET.copy()
    queryDict['user_email'] = user_email
    queryDict['request'] = request
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWeb = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWeb.isTrusted()
    siteName, siteList = madWeb.getSiteInfo()
    form = madweb.forms.SingleExpDefaultForm(queryDict, initial = {'isTrusted': isTrusted})
    if not form.is_valid():
        # new page
        form = madweb.forms.SingleExpDefaultForm(initial = {'isTrusted': isTrusted})
    responseDict['form'] = form
    responseDict['site_name'] = siteName
    responseDict['site_list'] = siteList
    responseDict['redirect_list'] = madWeb.getSingleRedirectList()
    if 'instruments' in request.GET:
        responseDict['instruments'] = request.GET['instruments']
    if 'years' in request.GET:
        responseDict['years'] = request.GET['years']
    if 'months' in request.GET:
        responseDict['months'] = request.GET['months']
    try:
        # add extra keys if choosing a file
        form.fields['file_list']
        responseDict['loader'] = 'loadSingleForm'
        responseDict['redirect'] = reverse('get_files')
        # handle the case with no files
        if len(form.fields['file_list'].choices) < 2:
            form2 = madweb.forms.SingleExpPlotsForm({'experiment_list':form['exp_id'].initial,
                                                     'request':request})
            form.fields['plot_list'] = form2.fields['plot_list']
    except:
        pass
    responseDict['bg_color'] = bg_color
    return render(request, 'madweb/single.html', responseDict)


def get_categories(request):
    """get_categories is a Ajax call that returns the categories select html to support the 
    single experiment UI.  Called when a user modifies the isGlobal checkbox.
    
    Inputs:
        request
    """
    queryDict = request.GET.copy()
    queryDict['request'] = request
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    form = madweb.forms.SingleExpDefaultForm(queryDict, initial = {'isTrusted': isTrusted})
    
    return render(request, 'madweb/categories.html', {'form': form})


def get_instruments(request):
    """get_instruments is a Ajax call that returns the instruments select html to support the 
    single experiment UI.  Called when a user modifies the categories select field.
    
    Inputs:
        request
    """
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    form = madweb.forms.SingleExpInstForm(request.GET, initial = {'isTrusted': isTrusted})
    
    return render(request, 'madweb/instruments.html', {'form': form})


def get_years(request):
    """get_years is a Ajax call that returns the years select html to support the 
    single experiment UI.  Called when a user modifies the instruments select field.
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    form = madweb.forms.SingleExpYearForm(request.GET, initial = {'isTrusted': isTrusted})
    
    is_global = madweb.forms.getIsGlobal([], request.GET)
    
    return render(request, 'madweb/years.html', {'isGlobal': is_global,
                                                    'form': form})
    
    
def get_months(request):
    """get_months is a Ajax call that returns the months select html to support the 
    single experiment UI.  Called when a user modifies the years select field.
    
    Inputs:
        request 
    """
    queryDict = request.GET.copy()
    queryDict['request'] = request
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    form = madweb.forms.SingleExpMonthForm(queryDict, initial = {'isTrusted': isTrusted})
    
    is_global = madweb.forms.getIsGlobal([], request.GET)
    year = int(request.GET['years'])
    kinst =int(request.GET['instruments'])
    
    return render(request, 'madweb/months.html', {'isGlobal': is_global,
                                                     'years': year,
                                                     'form': form})


def get_calendar(request):
    """get_calendar is a Ajax call that returns the calendar html  to support the 
    single experiment UI.  Called when a user selects month field.
    
    Inputs:
        request
    """
    is_global = madweb.forms.getIsGlobal([], request.GET)
    year = int(request.GET['years'])
    month = int(request.GET['months'])
    kinst =int(request.GET['instruments'])
    
    form = madweb.forms.SingleExpCalendarForm({'years': year,
                                               'months': month,
                                               'instruments': kinst,
                                               'request': request})
    
    return render(request, 'madweb/calendar.html', {'isGlobal': is_global,
                                                       'years': year, 
                                                       'months': month,
                                                       'instruments': kinst,
                                                       'form': form})
    
    
def populate_calendar_experiment(request):
    """populate_calendar_experiment is a ajax view that returns a json object used by the
    calender widget to populate itself.
    
    Inputs:
        request
    """
    is_global = madweb.forms.getIsGlobal([], request.GET)
    year = int(request.GET['years'])
    month = int(request.GET['months'])
    kinst =int(request.GET['instruments'])
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    madInstObj = madrigal.metadata.MadrigalInstrument(madDB)
    catId = madInstObj.getCategoryId(kinst)
    
    expDays = madWebObj.getDays(kinst, year, month)
    
    if len(expDays) == 0:
        expDays = madWebObj.getDays(kinst, year, month, optimize=False)
    
    color = "#999"
    jsonListFinal = []
    for expDay in expDays:
        newdate = '%i/%i/%i' % (expDay.day, expDay.month, expDay.year)
        urlperDate = reverse('view_single') 
        query_str = '?'
        if is_global:
            query_str += 'isGlobal=on&'
        query_str += 'categories=%i&instruments=%i&years=%i&months=%i&days=%i' % (catId, kinst, year,
                                                                                  expDay.month, expDay.day)
        urlperDate += query_str
        dayList = [newdate, "", urlperDate, color]
        jsonListFinal.append(dayList)
    
    return HttpResponse(json.dumps(jsonListFinal), content_type='application/json')


def get_files(request):
    """get_files is a Ajax call that returns the files select html to support the 
    single experiment UI.  Called when a user modifies the calendar or experiments fields.
    
    Inputs:
        request 
    """
    cookieDict = request.COOKIES
    user_email = cookieDict['user_email']
    queryDict = request.GET.copy()
    queryDict['user_email'] = user_email
    queryDict['request'] = request
    form = madweb.forms.SingleExpFileForm(queryDict)
    
    is_global = madweb.forms.getIsGlobal([], request.GET)
        
    return render(request, 'madweb/file_list.html', {'isGlobal': is_global,
                                                        'form': form,
                                                        'loader': 'loadSingleForm',
                                                        'redirect': reverse('get_files')})
    

def change_files(request):
    """change_files is a Ajax call that returns the files options html to support the 
    single experiment UI.  Called when a user modifies the files select field.
    
    Inputs:
        request 
    """
    expID =int(request.GET['experiment_list'])
    basename = request.GET['file_list']
    madDB = madrigal.metadata.MadrigalDB()
    queryDict = request.GET.copy()
    queryDict['request'] = request
    form = madweb.forms.SingleExpButtonsForm(request.GET)
    
    return render(request, 'madweb/file_buttons.html', {'form': form,
                                                        'plot_label': madDB.getPlotButtonLabel()})


def show_plots(request):
    """show_plots is a Ajax call that returns the files data html with plots to support the 
    single experiment UI.  Called when a user modifies the files select field.
    
    Inputs:
        request 
    """
    try:
        expID = int(request.GET['experiment_list'])
    except ValueError:
        # convert expPath to expID
        madDB = madrigal.metadata.MadrigalDB()
        madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
        expID = madWebObj.getExpIDFromExpPath(request.GET['experiment_list'], True)
        
    queryDict = request.GET.copy()
    queryDict['request'] = request
    form = madweb.forms.SingleExpPlotsForm(queryDict)
    
    return render(request, 'madweb/show_plots.html', {'form': form})


def download_as_is(request):
    """download_as_is is a Ajax call that returns the download as is html to support the 
    single experiment UI.  Called when a user selects download/as is link.
    
    Inputs:
        request 
    """
    cookieDict = request.COOKIES
    if not 'user_fullname' in cookieDict:
        return(HttpResponse('<p>Cookie with user_fullname required for downloadAsIs</p>'))
    user_fullname = urllib.parse.quote_plus(cookieDict['user_fullname'])
    user_email = cookieDict['user_email']
    user_affiliation = urllib.parse.quote_plus(cookieDict['user_affiliation'])
    expID =int(request.GET['experiment_list'])
    file_list = request.GET['file_list']
    form = madweb.forms.SingleExpDownloadAsIsForm({'format_select':file_list,
                                                   'expID': expID})
    
    return render(request, 'madweb/download_as_is.html', {'form': form, 'exp_id':expID,
                                                             'user_fullname':user_fullname,
                                                             'user_email':user_email,
                                                             'user_affiliation': user_affiliation})
    
    
def download_file_as_is(request):
    """download_file_as_is is a Ajax call that actually downloads a madrigal file.
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    user_fullname = urllib.parse.unquote_plus(request.GET['user_fullname'])
    user_email = request.GET['user_email']
    user_affiliation = urllib.parse.unquote_plus(request.GET['user_affiliation'])
    exp_id = request.GET['exp_id']
    basename = request.GET['basename']
    downloadFile = madWebObj.downloadFileAsIs(exp_id, basename, user_fullname, user_email, user_affiliation)
    f = open(downloadFile, 'rb')
    filename = os.path.basename(downloadFile)
    chunk_size = 8192
    file_type = mimetypes.guess_type(downloadFile)[0]
    if file_type is None:
        file_type = 'application/octet-stream'
    response = StreamingHttpResponse(FileWrapper(f, chunk_size),
                                     content_type=file_type)
    response['Content-Length'] = os.path.getsize(downloadFile)    
    response['Content-Disposition'] = "attachment; filename=%s" % (filename)
    response.set_cookie('fileDownload', 'true', path='/', samesite='Strict')
    return(response)


def print_as_is(request):
    """print_as_is is a Ajax call that returns the text of the ascii file to support the 
    single experiment UI if request.GET has key "text", or the length of the file to be
    downloaded if not.  Called when a user selects print/as is link.
    
    Inputs:
        request 
    """ 
    madDB = madrigal.metadata.MadrigalDB()
    madExpObj = madrigal.metadata.MadrigalExperiment(madDB)
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    madParmObj = madrigal.data.MadrigalParameters(madDB)
    
    cookieDict = request.COOKIES
    if not 'user_fullname' in cookieDict:
        return(HttpResponse('<p>Cookie with user_fullname required for printAsIs</p>'))
    user_fullname = urllib.parse.quote_plus(cookieDict['user_fullname'])
    user_email = cookieDict['user_email']
    user_affiliation = urllib.parse.quote_plus(cookieDict['user_affiliation'])
    expID =int(request.GET['experiment_list'])
    basename = request.GET['file_list']
    expDir = madExpObj.getExpDirByExpId(int(expID))
    if expDir is None:
        raise ValueError('No expDir found for exp_id %i' % (int(expID)))
    fullFilename = os.path.join(expDir, basename)
    
    # determine if we need to return the full file text, or just the size and name
    if 'text' in request.GET:
        madFileObj = madrigal.data.MadrigalFile(fullFilename, madDB)
        measParms = madFileObj.getMeasuredParmList()
        measParmMnemList = madParmObj.getParmMnemonicList(measParms) + madFileObj.getStandardParms(upper=True)
        measParmDescList = madParmObj.getParmDescriptionList(measParmMnemList)
        parmList = list(zip(measParmMnemList, measParmDescList))
        f = open(request.GET['text'])
        text = f.read()
        f.close()
        
        return render(request, 'madweb/print_as_is.html', {'text': text, 'parmList': parmList})
    
    else:
        tmpFilename = madWebObj.printFileAsIs(fullFilename, user_fullname, user_email, user_affiliation)
        filesize = os.path.getsize(tmpFilename)
        return(HttpResponse('%s:%s' % (filesize, tmpFilename)))
    
    
def list_records(request):
    """list_records is a Ajax call that returns the list records text.
    
    Inputs:
        request 
    """ 
    madDB = madrigal.metadata.MadrigalDB()
    madExpObj = madrigal.metadata.MadrigalExperiment(madDB)
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    
    expID =int(request.GET['experiment_list'])
    basename = request.GET['file_list']
    expDir = madExpObj.getExpDirByExpId(int(expID))
    if expDir is None:
        raise ValueError('No expDir found for exp_id %i' % (int(expID)))
    fullFilename = os.path.join(expDir, basename)
    
    text = madWebObj.listRecords(fullFilename)
    
    return render(request, 'madweb/list_records.html', {'expDir': expDir,
                                                           'basename': basename,
                                                           'text': text})
    
    
def view_record_plot(request):
    """view_record_plot returns the view individual record page.
    
    Inputs:
        request 
    """ 
    expDir = request.GET['expDir']
    basename = request.GET['basename']
    recno = int(request.GET['recno'])
    
    return render(request, 'madweb/view_record_plot.html', {'expDir': expDir,
                                                               'basename': basename,
                                                               'recno': recno})


def view_record_image(request):
    """view_record_plot is a Ajax call that returns the record plot.
    
    Inputs:
        request 
    """ 
    expDir = request.GET['expDir']
    basename = request.GET['basename']
    recno = int(request.GET['recno'])
    pngFiles = glob.glob(os.path.join(expDir, 'plots', basename, 'records/*%05i*.png' % (recno)))
    
    image_data = open(pngFiles[0], "rb").read()
    return HttpResponse(image_data, content_type="image/png")
    
    
    
    
def show_info(request):
    """show_info is a Ajax call that returns the text of the catalog/header text to support the 
    single experiment UI.  Called when a user selects show info link.
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    madExpObj = madrigal.metadata.MadrigalExperiment(madDB)
    
    expID =int(request.GET['experiment_list'])
    basename = request.GET['file_list']
    expDir = madExpObj.getExpDirByExpId(int(expID))
    if expDir is None:
        raise ValueError('No expDir found for exp_id %i' % (int(expID)))
    fullFilename = os.path.join(expDir, basename)
    
    madFileObj = madrigal.data.MadrigalFile(fullFilename, madDB)
    text = madFileObj.getCatalogHeaderStr()
    
    return render(request, 'madweb/show_info.html', {'text':text})


def show_doi(request):
    """show_doi is a Ajax call that returns the permanent url for references to support the 
    single experiment UI.  Called when a user selects show doi link.
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    madExpObj = madrigal.metadata.MadrigalExperiment(madDB)
    madInstObj = madrigal.metadata.MadrigalInstrument(madDB)
    
    expID =request.GET['experiment_list']
    basename = request.GET['file_list']
    expDir = madExpObj.getExpDirByExpId(int(expID))
    # get experiment PI and institution
    PI = madExpObj.getPIByExpId(int(expID))
    kinst = madExpObj.getKinstByExpId(int(expID))
    startDTList = madExpObj.getExpStartDateTimeByExpId(int(expID))
    yearStr = str(startDTList[0])
    if PI is None:
        PI = madInstObj.getContactName(kinst)
    institution = madInstObj.getContactAddress1(kinst)
    
    try:
        madFileObj = madrigal.metadata.MadrigalMetaFile(madDB, os.path.join(expDir, 'fileTab.txt'))
        url = madFileObj.getFileDOIUrlByFilename(basename)
    except:
        url = 'Unknown - please contact madrigal@haystack.mit.edu'
    
    return render(request, 'madweb/show_doi.html', {'url':url, 'PI': PI, 'year': yearStr,
                                                       'institution': institution})


def get_advanced(request):
    """get_advanced is a view that allows user to download/print files with selected parms
    and filters.
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWeb = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWeb.getSiteInfo()
    madExpObj = madrigal.metadata.MadrigalExperiment(madDB)
    webFormatObj = madrigal.ui.web.MadrigalWebFormat()
    madParmObj = madrigal.data.MadrigalParameters(madDB)
    parmList = webFormatObj.getFormat('Comprehensive')
    measParmList = []
    derivedParmList = []
    allParmList = []
    sureParmList = []
    
    if 'experiment_list' in request.GET:
        expID = int(request.GET['experiment_list'])
    else:
        return(HttpResponse('<p>experiment_list required for getAdvanced</p>'))
    basename = request.GET['file_list']
    type = request.GET['type']
    expDir = madExpObj.getExpDirByExpId(int(expID))
    if expDir is None:
        raise ValueError('No expDir found for exp_id %i' % (int(expID)))
    fullFilename = os.path.join(expDir, basename)
    expName, kindatDesc = madWeb.getInfoFromFile(fullFilename)
    madFileObj = madrigal.data.MadrigalFile(fullFilename, madDB)
    earliestTime = madFileObj.getEarliestTime()
    latestTime = madFileObj.getLatestTime()
    earliestDT = datetime.datetime(*earliestTime)
    latestDT = datetime.datetime(*latestTime)
    madFileObj.getMeasDervBothParmLists(parmList, measParmList, derivedParmList, allParmList, sureParmList)
    allParmDescList = madParmObj.getParmDescriptionList(allParmList)
    
    dataDict = {'type': type,
                'fullFilename': fullFilename,
                'madFileObj': madFileObj, 'parameters': [],
                'measParmList': measParmList, 'derivedParmList': derivedParmList,
                'allParmList': allParmList, 'allParmDescList': allParmDescList,
                'madDB': madDB, 'madParmObj': madParmObj}
    
    min_alt = madFileObj.getMinValidAltitude()
    max_alt = madFileObj.getMaxValidAltitude()
    try:
        float(min_alt)
        float(max_alt)
        dataDict['min_alt'] = '%9.2f' % (min_alt)
        dataDict['max_alt'] = '%9.2f' % (max_alt)
    except:
        pass
    
    if 'AZM' in allParmList:
        dataDict['min_az'] = '-180.0'
        dataDict['max_az'] = '180.0'
        dataDict['min_az2'] = '0.0'
        dataDict['max_az2'] = '0.0'
        
    if 'ELM' in allParmList:
        dataDict['min_el'] = '0.0'
        dataDict['max_el'] = '90.0'
        dataDict['min_el2'] = '0.0'
        dataDict['max_el2'] = '0.0'
        
    if 'PL' in allParmList:
        min_pl = madFileObj.getMinPulseLength()
        max_pl = madFileObj.getMaxPulseLength()
        try:
            float(min_pl)
            float(max_pl)
            dataDict['min_pl'] = '%9.2f' % (min_pl)
            dataDict['max_pl'] = '%9.2f' % (max_pl)
        except:
            pass
        
    if type == 'download':
        defaultFormat = 'Hdf5'
    else:
        defaultFormat = 'ascii'
    dataDict['formats'] = defaultFormat
    dataDict['missing'] = 'NaN'
    dataDict['start_date'] = earliestDT
    dataDict['end_date'] = latestDT
    
    
    isprintForm = madweb.forms.IsprintForm(dataDict)
    
    return render(request, 'madweb/get_advanced.html', {'form': isprintForm,
                                                           'parmList': isprintForm.parmList,
                                                           'measParmList': measParmList,
                                                           'site_name': siteName, 'site_list': siteList,
                                                           'expName': expName, 'kindatDesc': kindatDesc,
                                                           'basename': os.path.basename(fullFilename),
                                                           'type': type, 'bg_color': bg_color,
                                                           'datetime': True})
    
def advanced_download(request):
    """advanced_download is a view that downloads a file with selected parms
    and filters.
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    madWeb = madrigal.ui.web.MadrigalWeb(madDB, request)
    webFormatObj = madrigal.ui.web.MadrigalWebFormat()
    madParmObj = madrigal.data.MadrigalParameters(madDB)
    
    cookieDict = request.COOKIES
    if not 'user_fullname' in cookieDict:
        return(HttpResponse('<p>Cookie with user_fullname required for advancedDownload</p>'))
    user_fullname = urllib.parse.quote_plus(cookieDict['user_fullname'])
    user_email = cookieDict['user_email']
    user_affiliation = urllib.parse.quote_plus(cookieDict['user_affiliation'])
    parmList = webFormatObj.getFormat('Comprehensive')
    measParmList = []
    derivedParmList = []
    allParmList = []
    sureParmList = []
    madFileObj = madrigal.data.MadrigalFile(request.GET['fullFilename'], madDB)
    madFileObj.getMeasDervBothParmLists(parmList, measParmList, derivedParmList, allParmList, sureParmList)
    allParmDescList = madParmObj.getParmDescriptionList(allParmList)
    
    request.GET._mutable = True
    request.GET['madFileObj']=madFileObj
    request.GET['measParmList']=measParmList
    request.GET['derivedParmList']=derivedParmList
    request.GET['allParmList']=allParmList
    request.GET['allParmDescList']=allParmDescList
    request.GET['start_date'] = request.GET['start_date'].strip()
    request.GET['end_date'] = request.GET['end_date'].strip()
    # convert dates to datetime
    request.GET['start_date'] = datetime.datetime.strptime(request.GET['start_date'], '%Y-%m-%dT%H:%M:%S')
    request.GET['end_date'] = datetime.datetime.strptime(request.GET['end_date'], '%Y-%m-%dT%H:%M:%S')
    request.GET['madDB'] = madDB
    request.GET['madParmObj'] = madParmObj
    
    
    isprintForm = madweb.forms.IsprintForm(request.GET)

    
    if not isprintForm.is_valid():
        raise ValueError(str(isprintForm.errors))
    
    downloadFile = madWeb.downloadIsprintFileFromIsprintForm(isprintForm.cleaned_data, user_fullname, user_email, user_affiliation)
    
    
    f = open(downloadFile, 'rb')
    filename = os.path.basename(downloadFile)
    chunk_size = 8192
    file_type = mimetypes.guess_type(downloadFile)[0]
    if file_type is None:
        file_type = 'application/octet-stream'
    response = StreamingHttpResponse(FileWrapper(f, chunk_size),
                                     content_type=file_type)
    response['Content-Length'] = os.path.getsize(downloadFile)    
    response['Content-Disposition'] = "attachment; filename=%s" % (filename)
    return(response)


def advanced_print(request):
    """advanced_download is a view that print a file with selected parms
    and filters.
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWeb = madrigal.ui.web.MadrigalWeb(madDB, request)
    webFormatObj = madrigal.ui.web.MadrigalWebFormat()
    madParmObj = madrigal.data.MadrigalParameters(madDB)
    
    cookieDict = request.COOKIES
    if not 'user_fullname' in cookieDict:
        return(HttpResponse('<p>Cookie with user_fullname required for advancedPrint</p>'))
    user_fullname = urllib.parse.quote_plus(cookieDict['user_fullname'])
    user_email = cookieDict['user_email']
    user_affiliation = urllib.parse.quote_plus(cookieDict['user_affiliation'])
    
    parmList = webFormatObj.getFormat('Comprehensive')
    measParmList = []
    derivedParmList = []
    allParmList = []
    sureParmList = []
    madFileObj = madrigal.data.MadrigalFile(request.GET['fullFilename'], madDB)
    madFileObj.getMeasDervBothParmLists(parmList, measParmList, derivedParmList, allParmList, sureParmList)
    allParmDescList = madParmObj.getParmDescriptionList(allParmList)
    fullFilename = request.GET['fullFilename']
    expName, kindatDesc = madWeb.getInfoFromFile(fullFilename)
    
    request.GET._mutable = True
    request.GET['madFileObj']=madFileObj
    request.GET['measParmList']=measParmList
    request.GET['derivedParmList']=derivedParmList
    request.GET['allParmList']=allParmList
    request.GET['allParmDescList']=allParmDescList
    request.GET['start_date'] = request.GET['start_date'].strip()
    request.GET['end_date'] = request.GET['end_date'].strip()
    # convert dates to datetime
    request.GET['start_date'] = datetime.datetime.strptime(request.GET['start_date'], '%Y-%m-%dT%H:%M:%S')
    request.GET['end_date'] = datetime.datetime.strptime(request.GET['end_date'], '%Y-%m-%dT%H:%M:%S')
    request.GET['madDB'] = madDB
    request.GET['madParmObj'] = madParmObj
    
    isprintForm = madweb.forms.IsprintForm(request.GET)

    
    if not isprintForm.is_valid():
        raise ValueError(str(isprintForm.errors))
    
    downloadFile = madWeb.downloadIsprintFileFromIsprintForm(isprintForm.cleaned_data, user_fullname, user_email, user_affiliation)
    
    f = open(downloadFile, 'r')
    file_text = f.read()
    f.close()
    os.remove(downloadFile)
    return render(request, 'madweb/advanced_print.html', {'expName': expName, 'kindatDesc': kindatDesc,
                                                           'basename': os.path.basename(fullFilename),
                                                           'file_text': file_text, 'bg_color': bg_color})
    

@csrf_protect    
def view_list(request):
    """view_list is the list experiment view.
    """
    request = check_registration(request)

    if type(request) == HttpResponseRedirect:
        return(request)
    
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    siteName, siteList = madWebObj.getSiteInfo()
    responseDict = {'list_active': 'class="active"'}
    form = madweb.forms.ListExpForm(initial = {'isTrusted': isTrusted})
    responseDict['form'] = form
    responseDict['categoryList'] = form.categories
    responseDict['instrumentList'] = form.instruments
    responseDict['site_name'] = siteName
    responseDict['site_list'] = siteList
    responseDict['datetime'] = True
    responseDict['bg_color'] = bg_color
    
    return render(request, 'madweb/list.html', responseDict)


def list_experiments(request):
    """list_experiments is a view that lists all selected experiments.
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWeb = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWeb.isTrusted()
    siteName, siteList = madWeb.getSiteInfo()
    
    listForm = madweb.forms.ListExpForm(request.GET, initial = {'isTrusted': isTrusted})
    try:
        if not listForm.is_valid():
            return(HttpResponse(str(listForm.errors)))
    except KeyError:
        return(HttpResponse('<p>Missing arguments in list_experiments</p>'))
    
    kinstList = [int(kinst) for kinst in listForm.cleaned_data['instruments']]
    startDate = listForm.cleaned_data['start_date']
    startDT = datetime.datetime(startDate.year, startDate.month, startDate.day, startDate.hour, startDate.minute, startDate.second)
    endDate = listForm.cleaned_data['end_date']
    endDT = datetime.datetime(endDate.year, endDate.month, endDate.day, endDate.hour, endDate.minute, endDate.second)
    localOnly = not listForm.cleaned_data['isGlobal']
    expList = madWeb.getExperimentList(kinstList, startDT, endDT, localOnly)
    
    return render(request, 'madweb/list_experiments.html', {'expList':expList, 'localOnly':localOnly,
                                                               'list_active': 'class="active"', 'site_name': siteName, 
                                                               'site_list': siteList, 'bg_color': bg_color})


@csrf_protect
def show_experiment(request):
    """show_experiment call that returns the experiment page to support the list experiments UI.  
    
    Inputs:
        request 
    """
    request = check_registration(request)

    if type(request) == HttpResponseRedirect:
        return(request)
    
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    cookieDict = request.COOKIES
    user_email = cookieDict['user_email']
    queryDict = request.GET.copy()
    queryDict['user_email'] = user_email
    queryDict['request'] = request
    if 'show_plots' in queryDict:
        plotsForm = madweb.forms.SingleExpPlotsForm(queryDict)
    form = madweb.forms.SingleExpFileForm(queryDict)
    if 'show_plots' in queryDict:
        form.fields['plot_list'] = plotsForm.fields['plot_list']
    if len(form.fields['file_list'].choices) > 1:
        # this experiment has data files
        return render(request, 'madweb/show_experiment.html', {'list_active': 'class="active"',
                                                                  'form': form, 'site_name': siteName, 
                                                                  'site_list': siteList,
                                                                  'loader': 'loadPage',
                                                                  'bg_color': bg_color,
                                                                  'redirect': reverse('show_experiment')})
        
    else:
        # this experiment has no data files
        queryDict = request.GET.copy()
        queryDict['request'] = request
        form2 = madweb.forms.SingleExpPlotsForm(queryDict)
        exp_desc = form.fields['exp_desc'].label
        return render(request, 'madweb/show_exp_no_files.html', {'list_active': 'class="active"',
                                                                    'form': form2, 'exp_desc': exp_desc,
                                                                    'site_name': siteName, 
                                                                    'site_list': siteList,
                                                                    'loader': 'loadPage',
                                                                    'bg_color': bg_color,
                                                                    'redirect': reverse('show_experiment')})
        

@csrf_protect    
def show_experiment_v2(request):
    """show_experiment_v2 is a slight variant of show_experiment to accept old form
    calls from Madrigal2 sites.  
    
    Inputs:
        request 
    """
    request = check_registration(request)

    if type(request) == HttpResponseRedirect:
        return(request)
    
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    cookieDict = request.COOKIES
    user_email = cookieDict['user_email']
    queryDict = request.GET.copy()
    queryDict['user_email'] = user_email
    queryDict['experiment_list'] = queryDict['exp']
    queryDict['request'] = request
    form = madweb.forms.SingleExpFileForm(queryDict)
        
    return render(request, 'madweb/show_experiment.html', {'list_active': 'class="active"',
                                                              'form': form, 'site_name': siteName, 
                                                              'site_list': siteList,
                                                              'loader': 'loadPage',
                                                              'bg_color': bg_color,
                                                              'redirect': reverse('show_experiment')})
    
@csrf_protect    
def choose_script(request):
    """choose_script that returns the choose script page.  
    
    Inputs:
        request 
    """
    request = check_registration(request)

    if type(request) == HttpResponseRedirect:
        return(request)
    
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo() 
    return render(request, 'madweb/choose_script.html', {'script_active': 'class="active"', 'site_name': siteName, 
                                                            'site_list': siteList, 'bg_color': bg_color})


def download_as_is_script(request):
    """download_as_is_script that returns the download_as_is_script script page.  
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    siteName, siteList = madWebObj.getSiteInfo()
    responseDict = {'script_active': 'class="active"'}
    form = madweb.forms.DownloadAsIsScriptForm(initial = {'isTrusted': isTrusted})
    responseDict['form'] = form
    responseDict['categoryList'] = form.categories
    responseDict['instrumentList'] = form.instruments
    responseDict['kindatList'] = form.kindats
    responseDict['site_name'] = siteName
    responseDict['site_list'] = siteList
    responseDict['datetime'] = True
    responseDict['bg_color'] = bg_color
        
    return render(request, 'madweb/download_as_is_script.html', responseDict)


def generate_download_files_script(request):
    """generate_download_files_script is a Ajax call that returns the generated file download script.  
    
    Inputs:
        request
    """
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    form = madweb.forms.DownloadAsIsScriptForm(request.GET, initial = {'isTrusted': isTrusted})
    
    try:
        if not form.is_valid():
            raise ValueError('Form error: %s' % (form.errors))
    except KeyError:
        return(HttpResponse('<p>Missing arguments in generate_download_files_script</p>'))
    
    cookieDict = request.COOKIES
    if not 'user_fullname' in cookieDict:
        return(HttpResponse('<p>Cookie with user_fullname required for generateDownloadFilesScript</p>'))
    user_fullname = urllib.parse.quote_plus(cookieDict['user_fullname'])
    user_email = cookieDict['user_email']
    user_affiliation = urllib.parse.quote_plus(cookieDict['user_affiliation'])
    script_text = madWebObj.generateDownloadFileScriptFromForm(form.cleaned_data, user_fullname,
                                                               user_email, user_affiliation)
    return render(request, 'madweb/download_files_script.html', {'script_text': script_text})


def download_advanced_script(request):
    """download_advanced_script that returns the download_advanced_script script page.  
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    siteName, siteList = madWebObj.getSiteInfo()
    responseDict = {'script_active': 'class="active"'}
    form = madweb.forms.DownloadAdvancedScriptForm(initial = {'isTrusted': isTrusted})
    responseDict['form'] = form
    responseDict['categoryList'] = form.categories
    responseDict['instrumentList'] = form.instruments
    responseDict['kindatList'] = form.kindats
    responseDict['site_name'] = siteName
    responseDict['site_list'] = siteList
    responseDict['datetime'] = True
    responseDict['bg_color'] = bg_color
        
    return render(request, 'madweb/download_advanced_script.html', responseDict)


def generate_download_advanced_script(request):
    """generate_download_advanced_script is a Ajax call that returns the generated advanced download script.  
    
    Inputs:
        request
    """
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    form1 = madweb.forms.DownloadAdvancedScriptForm(request.GET, initial = {'isTrusted': isTrusted})
    
    try:
        if not form1.is_valid():
            raise ValueError('Form error: %s' % (form1.errors))
    except KeyError:
        return(HttpResponse('<p>Missing arguments in generate_download_advanced_script</p>'))
    
    form2 = madweb.forms.AdvScriptParmsForm(request.GET)
    try:
        if not form2.is_valid():
            raise ValueError('Form error: %s' % (form2.errors))
    except KeyError:
        return(HttpResponse('<p>Missing arguments in generate_download_advanced_script</p>'))
    
    form3 = madweb.forms.AdvScriptParmsFiltersForm(request.GET)
    try:
        if not form3.is_valid():
            raise ValueError('Form error: %s' % (form3.errors))
    except KeyError:
        return(HttpResponse('<p>Missing arguments in generate_download_advanced_script</p>'))
    
    cookieDict = request.COOKIES
    if not 'user_fullname' in cookieDict:
        return(HttpResponse('<p>Cookie with user_fullname required for generateAdvancedDownloadScript</p>'))
    user_fullname = urllib.parse.quote_plus(cookieDict['user_fullname'])
    user_email = cookieDict['user_email']
    user_affiliation = urllib.parse.quote_plus(cookieDict['user_affiliation'])
    script_text = madWebObj.generateGlobalIsprintScriptFromForm(form1.cleaned_data, form2.cleaned_data, 
                                                                form3.cleaned_data, user_fullname,
                                                                user_email, user_affiliation)
    return render(request, 'madweb/download_files_script.html', {'script_text': script_text})


def generate_parms_script(request):
    """generate_parms_script is a Ajax call that returns the generated parameter script.  
    
    Inputs:
        request
    """
    try:
        form = madweb.forms.AdvScriptParmsForm(request.GET)
    except ValueError:
        return(HttpResponse('<p>Missing arguments in generate_parms_script</p>'))
    return render(request, 'madweb/download_adv_parms_script.html', {'form': form,
                                                                        'parmList': form.parmList})
    
    
def generate_parms_filters_script(request):
    """generate_parms_filters_script is a Ajax call that returns the generated parameter filters script.  
    
    Inputs:
        request
    """
    try:
        form = madweb.forms.AdvScriptParmsFiltersForm(request.GET)
    except ValueError:
        return(HttpResponse('<p>Missing arguments in generate_parms_filters_script</p>'))
    return render(request, 'madweb/download_adv_parms_filters_script.html', {'form': form})


@csrf_protect
def ftp(request):
    """ftp creates the first ftp page listing instruments
    """
    request = check_registration(request)

    if type(request) == HttpResponseRedirect:
        return(request)
    
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    siteName, siteList = madWebObj.getSiteInfo()
    cookieDict = request.COOKIES
    if not 'user_fullname' in cookieDict:
        return(HttpResponse('<p>Cookie with user_fullname required for ftp</p>'))
    fullname = urllib.parse.quote_plus(cookieDict['user_fullname'])
    email = cookieDict['user_email']
    affiliation = urllib.parse.quote_plus(cookieDict['user_affiliation'])
    # create instrument with data list with tuple (instrument_name, kinst)
    madInstDataObj = madrigal.metadata.MadrigalInstrumentData(madDB, isTrusted)
    madInstList = [(instrument_name, kinst) for kinst, instrument_name, site_id in madInstDataObj.getInstruments(local=True)]
    return render(request, 'madweb/ftp_instruments.html', {'madInstList': madInstList, 'fullname': fullname,
                                                              'email': email, 'affiliation':affiliation, 'site_name': siteName, 
                                                              'site_list': siteList, 'bg_color': bg_color})


def ftp_instrument(request, fullname, email, affiliation, kinst):
    """ftp_instrument creates the first ftp instrument page listing years
    Inputs: kinst selected
    """
    kinst = int(kinst)
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    bg_color = madDB.getBackgroundColor()
    madInstDataObj = madrigal.metadata.MadrigalInstrumentData(madDB, isTrusted)
    madInstObj = madrigal.metadata.MadrigalInstrument(madDB)
    inst_name = madInstObj.getInstrumentName(kinst)
    yearList = madInstDataObj.getInstrumentYears(kinst)
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    return render(request, 'madweb/ftp_years.html',{'yearList':yearList, 'kinst':kinst,
                                                       'inst_name':inst_name, 'fullname': fullname,
                                                       'email': email, 'affiliation':affiliation, 
                                                       'site_name': siteName, 'site_list': siteList,
                                                       'bg_color': bg_color })


def ftp_year(request, fullname, email, affiliation, kinst, year):
    """ftp_year creates the first ftp year page listing kindats
    Inputs: kinst selected, year selected
    """
    kinst = int(kinst)
    year = int(year)
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madInstObj = madrigal.metadata.MadrigalInstrument(madDB)
    inst_name = madInstObj.getInstrumentName(kinst)
    madInstKindatObj = madrigal.metadata.MadrigalInstrumentKindats(madDB)
    kindatList = madInstKindatObj.getKindatListForInstrumentYear(kinst, year)
    madKindatObj = madrigal.metadata.MadrigalKindat(madDB)
    # create kindatDescList, a list of tuples of (kindat_desc, kindat) for that kinst, year
    kindatDescList = []
    for kindat in kindatList:
        kindatDescList.append((madKindatObj.getKindatDescription(kindat, kinst), kindat))
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    return render(request, 'madweb/ftp_kindats.html', {'kindatDescList': kindatDescList, 'year': year,
                                                          'kinst': kinst, 'inst_name':inst_name, 'fullname': fullname,
                                                          'email': email, 'affiliation':affiliation,
                                                          'site_name': siteName, 'site_list': siteList, 
                                                          'bg_color': bg_color })
    
    
def ftp_kindat(request, fullname, email, affiliation, kinst, year, kindat):
    """ftp_kindat creates the first ftp format page listing formats to choose from
    Inputs: kinst selected, year selected, kindat selected
    """
    kinst = int(kinst)
    kindat = int(kindat)
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madKindatObj = madrigal.metadata.MadrigalKindat(madDB)
    kindat_desc = madKindatObj.getKindatDescription(kindat, kinst)
    madInstObj = madrigal.metadata.MadrigalInstrument(madDB)
    inst_name = madInstObj.getInstrumentName(kinst)
    formatDescList =  [(formatDict[key], key) for key in  list(formatDict.keys())]
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    return render(request, 'madweb/ftp_formats.html', {'formatDescList': formatDescList, 'year': year,
                                                          'kinst': kinst, 'inst_name': inst_name, 'kindat': kindat,
                                                          'kindat_desc': kindat_desc, 'fullname': fullname,
                                                          'email': email, 'affiliation': affiliation,
                                                          'site_name': siteName, 'site_list': siteList, 
                                                          'bg_color': bg_color } )
    
    
def ftp_files(request, fullname, email, affiliation, kinst, year, kindat, format):
    """ftp_files creates the ftp files page listing individual files
    Inputs: kinst selected, year selected, kindat selected
    """
    kinst = int(kinst)
    year = int(year)
    dt = datetime.datetime(year,1,1) # speed up search
    kindat = int(kindat)
    if format not in ('hdf5', 'netCDF4', 'ascii'):
        raise ValueError('Unknown format %s' % (format))
    if format == 'netCDF4':
        thisExt = '.nc'
    elif format == 'ascii':
        thisExt = '.txt'
    format_desc = formatDict[format]
    # create a list of full names, where each item is a tuple of 
    # (fullFilename in Madrigal, output basename with correct extension, date string)
    fileList = []
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madKindatObj = madrigal.metadata.MadrigalKindat(madDB)
    kindat_desc = madKindatObj.getKindatDescription(kindat, kinst)
    madInstObj = madrigal.metadata.MadrigalInstrument(madDB)
    inst_name = madInstObj.getInstrumentName(kinst)
    pi = madInstObj.getContactName(kinst)
    pi_email = madInstObj.getContactEmail(kinst)
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    isTrusted = madWebObj.isTrusted()
    madExpObj = madrigal.metadata.MadrigalExperiment(madDB)
    startIndex = madExpObj.getStartPosition(dt) + 1
    for loop in (0,1):
        # we normally only loop once, but sometimes multi-year experiments require a slow full search
        if loop == 0:
            thisStartIndex = startIndex
        else:
            thisStartIndex = 0 # should only get to this case for rare multi-year experiments
        for i in range(thisStartIndex, madExpObj.getExpCount()):
            if kinst != madExpObj.getKinstByPosition(i):
                continue
            stTuple = madExpObj.getExpStartDateTimeByPosition(i)[0:6]
            etTuple = madExpObj.getExpEndDateTimeByPosition(i)[0:6]
            expTitle = madExpObj.getExpNameByPosition(i)
            sDT = datetime.datetime(*stTuple)
            eDT = datetime.datetime(*etTuple)
            if sDT.year > year:
                break
            if eDT.year < year:
                continue
            # apply security filter
            thisSecurity = madExpObj.getSecurityByPosition(i)
            if isTrusted == 0 and thisSecurity not in (0,2):
                continue
            dateStr = ' From %s to %s: %s' % (sDT.strftime('%Y-%m-%d %H:%M:%S'), eDT.strftime('%Y-%m-%d %H:%M:%S'), str(expTitle))
            expDir = madExpObj.getExpDirByPosition(i)
            # look at this exp for the right kindat
            try:
                madFileObj = madrigal.metadata.MadrigalMetaFile(madDB, os.path.join(expDir, 'fileTab.txt'))
            except:
                pass
            for j in range(madFileObj.getFileCount()):
                if madFileObj.getCategoryByPosition(j) not in (0,1):
                    # skip history and alternate files
                    continue
                if madFileObj.getKindatByPosition(j) != kindat:
                    continue
                thisSecurity = madFileObj.getAccessByPosition(j)
                if isTrusted == 0 and thisSecurity not in (0,2):
                    continue
                statusStr = ' : %s' % (str(madFileObj.getStatusByPosition(j)))
                fullFilename = os.path.join(expDir, madFileObj.getFilenameByPosition(j))
                fullBasename = os.path.basename(fullFilename)
                if format != 'hdf5':
                    base, file_extension = os.path.splitext(fullFilename)
                    basename = os.path.basename(base + thisExt)
                else:
                    basename = os.path.basename(fullFilename)
                # make sure this file isn't too big to create a cache
                file_size = os.path.getsize(fullFilename)
                if file_size > maxSize and format != 'hdf5':
                    # make sure cached file exists before adding
                    if format == 'netCDF4':
                        cachedFile = os.path.join(expDir, 'overview', fullBasename + thisExt)
                    else:
                        cachedFile = os.path.join(expDir, 'overview', fullBasename + thisExt + '.gz')
                    if not os.path.exists(cachedFile):
                        continue
                fileList.append((urllib.parse.quote_plus(fullFilename), basename, dateStr + statusStr))
                
        if len(fileList) > 0:
            break # usually we avoid the slow full loop
            
            
    siteName, siteList = madWebObj.getSiteInfo()
            
    return render(request, 'madweb/ftp_files.html', {'fullFilenames': fileList, 'year': year, 'kindat_desc': kindat_desc,
                                                        'kinst': kinst, 'inst_name':inst_name, 'fullname': fullname,
                                                        'kindat': kindat, 'format': format, 'format_desc': format_desc,
                                                        'email': email, 'affiliation':affiliation,
                                                        'site_name': siteName, 'site_list': siteList, 
                                                        'pi_email': pi_email, 'pi_name': pi,
                                                        'bg_color': bg_color})
    
    
def ftp_download(request, user_fullname, user_email, user_affiliation, kinst, year, kindat, format, fullHdf5Filename):
    """ftp_download creates the first ftp kindat page listing individual files
    Inputs: kinst selected, year selected, kindat selected
    """
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    user_fullname = urllib.parse.unquote_plus(user_fullname)
    user_affiliation = urllib.parse.unquote_plus(user_affiliation)
    fullHdf5Filename = urllib.parse.unquote_plus(fullHdf5Filename)
    fullFilename = madWebObj.downloadFullFileAsIs(fullHdf5Filename, format, user_fullname, user_email, user_affiliation)
    
    f = open(fullFilename, 'rb')
    filename = os.path.basename(fullFilename)
    chunk_size = 8192
    file_type = mimetypes.guess_type(fullFilename)[0]
    if file_type is None:
        file_type = 'application/octet-stream'
    response = StreamingHttpResponse(FileWrapper(f, chunk_size),
                                     content_type=file_type)
    response['Content-Length'] = os.path.getsize(fullFilename)    
    response['Content-Disposition'] = "attachment; filename=%s" % (filename)
    return(response)


@csrf_protect
def ftp_multiple_download(request):
    """ftp_download creates the first ftp kindat page listing individual files
    Inputs: kinst selected, year selected, kindat selected
    """
    if request.method == 'POST':
        reqDict = request.POST
    else:
        reqDict = request.GET
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    user_fullname = urllib.parse.unquote_plus(reqDict.get('user_fullname'))
    user_email = reqDict.get('user_email')
    user_affiliation = urllib.parse.unquote_plus(reqDict.get('user_affiliation'))
    format = reqDict.get('format')
    fileList = reqDict.getlist('fullFilename')
    fileList = [urllib.parse.unquote_plus(filename) for filename in fileList]
    if len(fileList) > 10:
        # send user an email with warning
        tmpDir = os.path.join(madDB.getMadroot(), 'experiments/stage')
        fullFilename = os.path.join(tmpDir, 'result_error_%06i.txt' % (random.randint(0,999999)))
        f = open(fullFilename, 'w')
        f.write('Error - you requested %i files, maximum is 10\n' % (len(fileList)))
        f.close()
    else:
        fullFilename = madWebObj.downloadMultipleFiles(fileList, format, user_fullname, user_email, user_affiliation)
    
    f = open(fullFilename, 'rb')
    filename = os.path.basename(fullFilename)
    chunk_size = 8192
    file_type = mimetypes.guess_type(fullFilename)[0]
    if file_type is None:
        file_type = 'application/octet-stream'
    response = StreamingHttpResponse(FileWrapper(f, chunk_size),
                                     content_type=file_type)
    response['Content-Length'] = os.path.getsize(fullFilename)    
    response['Content-Disposition'] = "attachment; filename=%s" % (filename)
    return(response)

    
def instrument_metadata(request):
    """instrument_metadata returns the instrument_metadata page.  
    
    Inputs:
        request 
    """
    # create a list of tuples of (kinst, name, category, latitude, longitude, altitude, pi, pi_email, mnemonic)
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    madInstObj = madrigal.metadata.MadrigalInstrument(madDB)
    instList = []
    for name, mnemonic, kinst, category, catID in madInstObj.getOrderedInstrumentList():
        latitude = madInstObj.getLatitude(kinst)
        longitude = madInstObj.getLongitude(kinst)
        altitude = madInstObj.getAltitude(kinst)
        pi = madInstObj.getContactName(kinst)
        pi_email = madInstObj.getContactEmail(kinst)
        instList.append((kinst, name, category, latitude, longitude, altitude, pi, pi_email, mnemonic))
    
    responseDict = {'inst_active': 'class="active"', 'instList': instList,
                    'site_name': siteName, 'site_list': siteList, 'bg_color': bg_color}
    return render(request, 'madweb/instrument_metadata.html', responseDict)


def site_metadata(request):
    """site_metadata returns the site_metadata page.  
    
    Inputs:
        request 
    """
    # create a list of tuples of (siteId, name, url, contact, contact email, version)
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, otherSiteList = madWebObj.getSiteInfo()
    madSiteObj = madrigal.metadata.MadrigalSite(madDB)
    siteList = []
    for siteId, siteName in madSiteObj.getSiteList():
        if madSiteObj.getSiteServer(siteId).find('http') == -1:
            url = 'http://' + os.path.join(madSiteObj.getSiteServer(siteId),
                                           madSiteObj.getSiteDocRoot(siteId))
        else:
            url = os.path.join(madSiteObj.getSiteServer(siteId),
                               madSiteObj.getSiteDocRoot(siteId))
        contact = madSiteObj.getSiteContactName(siteId)
        contact_email = madSiteObj.getSiteEmail(siteId)
        version = madSiteObj.getSiteVersion(siteId)
        siteList.append((siteId, siteName, url, contact, contact_email, version))
    
    responseDict = {'site_active': 'class="active"', 'siteList': siteList,
                    'site_name': siteName, 'site_list': otherSiteList, 'bg_color': bg_color}
    return render(request, 'madweb/site_metadata.html', responseDict)


def parameter_metadata(request):
    """parameter_metadata returns the site_metadata page.  
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    madParmObj = madrigal.data.MadrigalParameters(madDB)
    madParmCatObj = madrigal.metadata.MadrigalParmCategory(madDB)
    parmDict = {} # key is category string, value is list of category tuples (mnemonic, description, units, code)
    parmList = [] # list of tuples, each tuple either a single category, or (mnemonic, description, units, code)
    categoryList = []
    categoryUrlList = []
    for mnemonic in madParmObj.getSortedMnemonicList():
        description = madParmObj.getSimpleParmDescription(mnemonic)
        units = madParmObj.getParmUnits(mnemonic)
        code = madParmObj.getParmCodeFromMnemonic(mnemonic)
        category = madParmObj.getParmCategory(mnemonic)
        if category is None:
            # deprecated prolog parm
            continue
        if category in list(parmDict.keys()):
            parmDict[category].append((mnemonic, description, units, code))
        else:
            parmDict[category] = [(mnemonic, description, units, code)]
            
    # now loop through all categories
    for thisCategory, catId in madParmCatObj.getCategoryList():
        parmList.append((thisCategory,))
        categoryList.append(thisCategory)
        categoryAnchor = thisCategory.replace(' ','_')
        categoryUrlList.append('<a href="#%s">%s</a>' % (categoryAnchor, thisCategory))
        for values in parmDict[thisCategory]:
            parmList.append(values)
    
    responseDict = {'parm_active': 'class="active"', 'parmList': parmList,
                    'categoryUrlList':categoryUrlList,
                    'site_name': siteName, 'site_list': siteList, 'bg_color': bg_color}
    return render(request, 'madweb/parameter_metadata.html', responseDict)


def kindat_metadata(request):
    """kindat_metadata returns the kindat_metadata page.  
    
    Inputs:
        request 
    """
    # create a list of tuples of (kindat, description, kinst, instrument_name)
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madKindatObj = madrigal.metadata.MadrigalKindat(madDB)
    madInstObj = madrigal.metadata.MadrigalInstrument(madDB)
    madInstKindatObj = madrigal.metadata.MadrigalInstrumentKindats(madDB)
    # create a dict of key = kindat code, value list of associated instruments
    kindatDict = {}
    for name, mnem, kinst in madInstObj.getInstrumentList():
        thisKindatList = madInstKindatObj.getKindatListForInstruments(kinst)
        for kindat in thisKindatList:
            if kindat not in kindatDict:
                kindatDict[kindat] = [kinst]
            else:
                kindatDict[kindat].append(kinst)
    
    kindatList = []
    for description, code_str in madKindatObj.getKindatList():
        try:
            kinst, kindat = code_str.split('_')
            instName = madInstObj.getInstrumentName(int(kinst))
        except:
            kindat = code_str
            try:
                kinst = str(kindatDict[int(kindat)][0])
                instName = madInstObj.getInstrumentName(int(kinst))
            except KeyError:
                kinst = '-'
                instName = 'Unspecified'
        kindatList.append((kindat, description, kinst, instName))
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    
    responseDict = {'kindat_active': 'class="active"', 'kindatList': kindatList,
                    'site_name': siteName, 'site_list': siteList, 'bg_color': bg_color}
    return render(request, 'madweb/kindat_metadata.html', responseDict)


def madrigal_calculator(request):
    """madrigal_calculator returns the Madrigal Calculator page.  
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    # original blank form
    madCalculatorForm = madweb.forms.MadCalculatorForm()
    parmList = [(parm, madCalculatorForm.parmDescDict[parm]) for parm in list(madCalculatorForm.parmDescDict.keys())]
    return render(request, 'madweb/madrigal_calculator.html', {'madCalculator_active': 'class="active"',
                                                                  'form': madCalculatorForm,
                                                                  'parmList': parmList,
                                                                  'site_name': siteName, 'site_list': siteList, 
                                                                  'bg_color': bg_color, 'datetime': True})
    
def madrigal_calculator_output(request):
    """madrigal_calculator returns the output from the Madrigal Calculator page.  
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    
    madCalculatorForm = madweb.forms.MadCalculatorForm(request.GET)
    
    try:
        if not madCalculatorForm.is_valid():
            return(HttpResponse(str(madCalculatorForm.errors)))
    except KeyError:
        return(HttpResponse('<p>Missing arguments in madCalculatorOutput</p>'))
    
    text = madWebObj.runMadrigalCalculatorFromForm(madCalculatorForm.cleaned_data)
    
    return render(request, 'madweb/madrigal_calculator_output.html', {'madCalculator_active': 'class="active"',
                                                                         'text': text,
                                                                         'site_name': siteName, 'site_list': siteList, 
                                                                         'bg_color': bg_color})
    
    
def get_metadata(request):
    """get_metadata allows local metadata files to be downloaded.  
    
    Inputs:
        request 
    """
    fileDict = {'0':'expTab.txt',
                '1': 'fileTab.txt',
                '3': 'instTab.txt',
                '4': 'parmCodes.txt',
                '5': 'siteTab.txt',
                '6': 'typeTab.txt',
                '7': 'instKindatTab.txt',
                '8': 'instParmTab.txt',
                '9': 'madCatTab.txt',
                '10': 'instType.txt'}
    form = madweb.forms.GetMetadataForm(request.GET)
    if form.is_valid():
        madDB = madrigal.metadata.MadrigalDB()
        downloadFile = os.path.join(madDB.getMetadataDir(), 
                                    fileDict[form.cleaned_data['fileType']])
        

        f = open(downloadFile, 'rb')
        filename = os.path.basename(downloadFile)
        chunk_size = 8192
        response = StreamingHttpResponse(FileWrapper(f, chunk_size),
                                         content_type=mimetypes.guess_type(downloadFile)[0])
        response['Content-Length'] = os.path.getsize(downloadFile)    
        response['Content-Disposition'] = "attachment; filename=%s" % (filename)
        return(response)
    
    else:
        madDB = madrigal.metadata.MadrigalDB()
        bg_color = madDB.getBackgroundColor()
        form = madweb.forms.GetMetadataForm()
        return render(request, 'madweb/get_metadata.html', {'form': form, 'bg_color': bg_color})
    
    
def looker_main(request):
    """looker_main loads the main looker selection form.  
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    lookerSelectForm = madweb.forms.LookerSelectForm()
    return render(request, 'madweb/looker_main.html', {'looker_active': 'class="active"',
                                                          'form': lookerSelectForm,
                                                          'site_name': siteName, 'site_list': siteList,
                                                          'bg_color': bg_color})


def looker_form(request):
    """looker_form loads the appropriate looker form.  
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    if not 'looker_options' in request.GET:
        return(HttpResponse('<p>looker form requires looker_options</p>'))
    form = madweb.forms.LookerSelectForm(request.GET)
    if form.is_valid():
        option = form.cleaned_data['looker_options']
        if option == '1':
            form = madweb.forms.LookerGeodeticRadar()
            return render(request, 'madweb/looker_geodetic_to_radar.html', {'looker_active': 'class="active"',
                                                                               'form': form,
                                                                               'site_name': siteName, 'site_list': siteList,
                                                                               'bg_color': bg_color})
        elif option == '2':
            form = madweb.forms.LookerGeomagRadar()
            return render(request, 'madweb/looker_geomagnetic_to_radar.html', {'looker_active': 'class="active"',
                                                                                  'form': form,
                                                                                  'site_name': siteName, 'site_list': siteList,
                                                                                  'bg_color': bg_color})
        elif option == '3':
            form = madweb.forms.LookerGeomagFromGeodetic()
            return render(request, 'madweb/looker_geomagnetic_from_geodetic.html', {'looker_active': 'class="active"',
                                                                                       'form': form,
                                                                                       'site_name': siteName, 'site_list': siteList,
                                                                                       'bg_color': bg_color})
        elif option == '4':
            form = madweb.forms.LookerGeomagFromRadar()
            return render(request, 'madweb/looker_geomagnetic_from_radar.html', {'looker_active': 'class="active"',
                                                                                    'form': form,
                                                                                    'site_name': siteName, 'site_list': siteList,
                                                                                    'bg_color': bg_color})
        elif option == '5':
            form = madweb.forms.LookerFieldLineFromRadar()
            return render(request, 'madweb/looker_field_line_from_radar.html', {'looker_active': 'class="active"',
                                                                                   'form': form,
                                                                                   'site_name': siteName, 'site_list': siteList,
                                                                                   'bg_color': bg_color})
        elif option == '6':
            form = madweb.forms.LookerFieldLineFromGeodetic()
            return render(request, 'madweb/looker_field_line_from_geodetic.html', {'looker_active': 'class="active"',
                                                                                      'form': form,
                                                                                      'site_name': siteName, 'site_list': siteList,
                                                                                      'bg_color': bg_color})
        elif option == '7':
            form = madweb.forms.LookerFieldLineFromApex()
            return render(request, 'madweb/looker_field_line_from_apex.html', {'looker_active': 'class="active"',
                                                                                  'form': form,
                                                                                  'site_name': siteName, 'site_list': siteList,
                                                                                  'bg_color': bg_color})
        elif option == '8':
            form = madweb.forms.LookerConjugateFromGeodetic()
            return render(request, 'madweb/looker_conjugate_from_geodetic.html', {'looker_active': 'class="active"',
                                                                                     'form': form,
                                                                                     'site_name': siteName, 'site_list': siteList,
                                                                                     'bg_color': bg_color,
                                                                                     'datetime': True})
    else:
        raise ValueError(str(form.errors))
    
    
def looker_output(request):
    """looker_output loads the appropriate looker output.  
    
    Inputs:
        request 
    """
    madDB = madrigal.metadata.MadrigalDB()
    bg_color = madDB.getBackgroundColor()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    siteName, siteList = madWebObj.getSiteInfo()
    
    if not 'looker_options' in request.GET:
        return(HttpResponse('<p>looker missing arguments</p>'))
    
    if request.GET['looker_options'] == "1":
        form = madweb.forms.LookerGeodeticRadar(request.GET)
        if form.is_valid():
            text = madWebObj.runLookerFromForm(form.cleaned_data)
            return render(request, 'madweb/looker_output.html', {'looker_active': 'class="active"',
                                                                    'type': 'Az, El, Range to Geodetic points',
                                                                    'text': text,
                                                                    'site_name': siteName, 'site_list': siteList,
                                                                    'bg_color': bg_color})
        else:
            raise ValueError(str(form.errors))
    elif request.GET['looker_options'] == "2":
        form = madweb.forms.LookerGeomagRadar(request.GET)
        if form.is_valid():
            text = madWebObj.runLookerFromForm(form.cleaned_data)
            return render(request, 'madweb/looker_output.html', {'looker_active': 'class="active"',
                                                                    'type': 'Az, El, Range to Geomagnetic (apex) points',
                                                                    'text': text,
                                                                    'site_name': siteName, 'site_list': siteList,
                                                                    'bg_color': bg_color})
        else:
            raise ValueError(str(form.errors))
    elif request.GET['looker_options'] == "3":
        form = madweb.forms.LookerGeomagFromGeodetic(request.GET)
        if form.is_valid():
            text = madWebObj.runLookerFromForm(form.cleaned_data)
            return render(request, 'madweb/looker_output.html', {'looker_active': 'class="active"',
                                                                    'type': 'Apex Geomagnetic coordinates from Geodetic grid',
                                                                    'text': text,
                                                                    'site_name': siteName, 'site_list': siteList,
                                                                    'bg_color': bg_color})
        else:
            raise ValueError(str(form.errors))
    elif request.GET['looker_options'] == "4":
        form = madweb.forms.LookerGeomagFromRadar(request.GET)
        if form.is_valid():
            text = madWebObj.runLookerFromForm(form.cleaned_data)
            return render(request, 'madweb/looker_output.html', {'looker_active': 'class="active"',
                                                                    'type': 'Apex Geomagnetic and geodetic coordinates and aspect angle from a grid of azimuth, elevation, and range',
                                                                    'text': text,
                                                                    'site_name': siteName, 'site_list': siteList,
                                                                    'bg_color': bg_color})
        else:
            raise ValueError(str(form.errors))
    elif request.GET['looker_options'] == "5":
        form = madweb.forms.LookerFieldLineFromRadar(request.GET)
        if form.is_valid():
            text = madWebObj.runLookerFromForm(form.cleaned_data)
            return render(request, 'madweb/looker_output.html', {'looker_active': 'class="active"',
                                                                    'type': 'Field line coordinates for a field line set by radar parameters',
                                                                    'text': text,
                                                                    'site_name': siteName, 'site_list': siteList,
                                                                    'bg_color': bg_color})
        else:
            raise ValueError(str(form.errors))
    elif request.GET['looker_options'] == "6":
        form = madweb.forms.LookerFieldLineFromGeodetic(request.GET)
        if form.is_valid():
            text = madWebObj.runLookerFromForm(form.cleaned_data)
            return render(request, 'madweb/looker_output.html', {'looker_active': 'class="active"',
                                                                    'type': 'Field line coordinates and radar look parameters for given field line',
                                                                    'text': text,
                                                                    'site_name': siteName, 'site_list': siteList,
                                                                    'bg_color': bg_color})
        else:
            raise ValueError(str(form.errors))
    elif request.GET['looker_options'] == "7":
        form = madweb.forms.LookerFieldLineFromApex(request.GET)
        if form.is_valid():
            text = madWebObj.runLookerFromForm(form.cleaned_data)
            return render(request, 'madweb/looker_output.html', {'looker_active': 'class="active"',
                                                                    'type': 'Field line coordinates and radar look parameters for given field line',
                                                                    'text': text,
                                                                    'site_name': siteName, 'site_list': siteList,
                                                                    'bg_color': bg_color})
        else:
            raise ValueError(str(form.errors))
    elif request.GET['looker_options'] == "8":
        form = madweb.forms.LookerConjugateFromGeodetic(request.GET)
        if form.is_valid():
            text = madWebObj.runLookerFromForm(form.cleaned_data)
            return render(request, 'madweb/looker_output.html', {'looker_active': 'class="active"',
                                                                    'type': 'Point/Magnetic Conjugate Point vs Latitude, Longitude, Altitude',
                                                                    'datetime': form.cleaned_data['datetime'],
                                                                    'text': text,
                                                                    'site_name': siteName, 'site_list': siteList,
                                                                    'bg_color': bg_color})
        else:
            raise ValueError(str(form.errors))
        
    else:
        raise ValueError('Unknown looker_option <%s>' % (str(request.GET['looker_options'])))
    
    
  
def get_version_service(request):
    """get_version_service runs the getVersionService.py service.  
    
    Inputs:
        request (ignored)
        
        Returns a single line of text, with the version in the form <major_version_int>.<minor_version_int>[.<sub_version_int>]
    """
    madDB = madrigal.metadata.MadrigalDB()
    siteID = madDB.getSiteID()
    madSiteObj = madrigal.metadata.MadrigalSite(madDB)
    return(HttpResponse(madSiteObj.getSiteVersion(siteID)))
    
    
   
def get_instruments_service(request):
    """get_instruments_service runs the getInstrumentsService.py service.  
    
    Inputs:
        request (ignored)
        
        Returns comma-delimited data, one line for each experiment, with the following fields:

        1. instrument.name  Example: 'Millstone Hill Incoherent Scatter Radar'

        2. instrument.code Example: 30

        3. instrument.mnemonic (3 char string) Example: 'mlh'

        4. instrument.latitude  Example: 45.0

        5. instrument.longitude  Example: 110.0

        6. instrument.altitude   Example: 0.015 (km) 
        
        7. instrument.category  Example: 'Incoherent Scatter Radars'
        
        8. contact name
        
        9. contact email
    """
    # create MadrigalDB obj
    madDBObj = madrigal.metadata.MadrigalDB()

    # create MadrigalInstument object
    madInst = madrigal.metadata.MadrigalInstrument(madDBObj)

    # get instrument list
    instList = madInst.getInstrumentList()

    # loop through each instrument
    instStr = ''
    for inst in instList:
        name = inst[0]
        code = inst[2]
        mnemonic = inst[1]
        latitude = madInst.getLatitude(code)
        if latitude == None:
            latitude = 0.0
        longitude = madInst.getLongitude(code)
        if longitude == None:
            longitude = 0.0
        altitude = madInst.getAltitude(code)
        if altitude == None:
            altitude = 0.0
        category = madInst.getCategory(code)
        if category == None:
            category = ''
        # print data
        contactName = madInst.getContactName(code)
        contactEmail = madInst.getContactEmail(code)
        instStr += '%s,%i,%s,%f,%f,%f,%s,%s,%s\n' % (name,
                                                     code,
                                                     mnemonic,
                                                     latitude,
                                                     longitude,
                                                     altitude,
                                                     category,
                                                     str(contactName),
                                                     str(contactEmail))
        
    return render(request, 'madweb/service.html', {'text': instStr})


def get_experiments_service(request):
    """get_experiments_service runs the getExperimentsService.py service.  
    
    Inputs:
        request/url - contains arguments:
        
            code - one or more kindat values
            
            startyear, startmonth, startday, starthour, startmin, startsec
            
            endyear, endmonth, endday, endhour, endmin, endsec
            
            local (defaults to True)
            
    Returns comma-delimited data, one line for each experiment, with the following fields:

        1. experiment.id (int) Example: 10000111
        
        2. experiment.url (string) Example: 'http://www.haystack.mit.edu/cgi-bin/madtoc/1997/mlh/03dec97'
        
        3. experiment.name (string) Example: 'Wide Latitude Substorm Study'
        
        4. experiment.siteid (int) Example: 1
        
        5. experiment.sitename (string) Example: 'Millstone Hill Observatory'
        
        6. experiment.instcode (int) Code of instrument. Example: 30
        
        7. experiment.instname (string) Instrument name. Example: 'Millstone Hill Incoherent Scatter Radar'
        
        8. experiment.start year (int) year of experiment start
        
        9. experiment.start month (int) month of experiment start
        
        10. experiment.start day (int) day of experiment start
        
        11. experiment.start hour (int) hour of experiment start
        
        12. experiment.start minute (int) min of experiment start
        
        13. experiment.start second (int) sec of experiment start
        
        14. experiment.end year (int) year of experiment end
        
        15. experiment.end month (int) month of experiment end
        
        16. experiment.end day (int) day of experiment end
        
        17. experiment.end hour (int) hour of experiment end
        
        18. experiment.end minute (int) min of experiment end
        
        19. experiment.end second (int) sec of experiment end
        
        20. experiment.isLocal (int) 1 if local, 0 if not
        
        21.experiment.PI (string) Experiment PI name Example: 'Phil Erickson'

        22. experiment.PIEmail (string) Experiment PI email Example: 'perickson@haystack.mit.edu'
        
        23. utc timestamp of last update to experiment
        
        24. security value
        
    """
    codeList = request.GET.getlist('code')
    codeList = [int(code) for code in codeList]
    startyear = int(request.GET['startyear'])
    startmonth = int(request.GET['startmonth'])
    startday = int(request.GET['startday'])
    starthour = int(request.GET['starthour'])
    startmin = int(request.GET['startmin'])
    startsec = int(request.GET['startsec'])
    endyear = int(request.GET['endyear'])
    endmonth = int(request.GET['endmonth'])
    endday = int(request.GET['endday'])
    endhour = int(request.GET['endhour'])
    endmin = int(request.GET['endmin'])
    endsec = int(request.GET['endsec'])
    try:
        local = int(request.GET['local'])
    except:
        local = 1
    
    # if startsec or endsec in (60, 61), handle correctly
    if startsec in (60, 61):
        tmpTime = datetime.datetime(startyear,
                                    startmonth,
                                    startday,
                                    starthour,
                                    startmin,
                                    59)
        tmpTime += datetime.timedelta(0, startsec - 59)
        startyear = tmpTime.year
        startmonth = tmpTime.month
        startday = tmpTime.day
        starthour = tmpTime.hour
        startmin = tmpTime.minute
        startsec = tmpTime.second

    if endsec in (60, 61):
        tmpTime = datetime.datetime(endyear,
                                    endmonth,
                                    endday,
                                    endhour,
                                    endmin,
                                    59)
        tmpTime += datetime.timedelta(0, endsec - 59)
        endyear = tmpTime.year
        endmonth = tmpTime.month
        endday = tmpTime.day
        endhour = tmpTime.hour
        endmin = tmpTime.minute
        endsec = tmpTime.second
        
    # if codeList is empty or contains 0, change it to only contain 0
    if len(codeList) == 0 or 0 in codeList:
        codeList = [0]
        
    retStr = ''

    # create MadrigalDB obj
    madDBObj = madrigal.metadata.MadrigalDB()

    # get the local site id
    localSiteId = madDBObj.getSiteID()

    # create MadrigalInstrument obj to convert kinst to instrument names
    madInstObj = madrigal.metadata.MadrigalInstrument(madDBObj)

    # create MadrigalSite obj to convert site id to site name
    madSiteObj = madrigal.metadata.MadrigalSite(madDBObj)
    
    madWebObj = madrigal.ui.web.MadrigalWeb(madDBObj, request)
    trusted = madWebObj.isTrusted()

    # create starttime for filter, if possible
    if startyear != None:
        startTimeFilter = datetime.datetime(startyear,
                        startmonth,
                        startday,
                        starthour,
                        startmin,
                        startsec) 
    else:
        startTimeFilter = None

    # create endtime for filter, if possible
    if endyear != None:
        endTimeFilter = datetime.datetime(endyear,
                          endmonth,
                      endday,
                      endhour,
                      endmin,
                      endsec) 
    else:
        endTimeFilter = None

    # create MadrigalExperiments for local or all files
    if local == 1:
        madExpObj = madrigal.metadata.MadrigalExperiment(madDBObj)
    else:
        # use file expTabAll.txt to get all experiments
        filename = madDBObj.getMadroot()
        if filename[-1] != '/':
            filename += '/'
        filename += 'metadata/expTabAll.txt'
        madExpObj = madrigal.metadata.MadrigalExperiment(madDBObj, filename)
        
    madExpObj.sortByDateSite()

    # loop through the data
    if not startTimeFilter is None:
        position = madExpObj.getStartPosition(startTimeFilter)
    else:
        position = 0
    while(True):
        thisId = madExpObj.getExpIdByPosition(position)
        # check for end
        if thisId == None:
            break
        thisUrl = madExpObj.getExpUrlByPosition(position)
        thisName = madExpObj.getExpNameByPosition(position)
        thisSiteId = madExpObj.getExpSiteIdByPosition(position)
        thisSiteName = madSiteObj.getSiteName(thisSiteId)
        thisInstCode = madExpObj.getKinstByPosition(position)
        thisInstName =madInstObj.getInstrumentName(thisInstCode)
        thisStart = madExpObj.getExpStartDateTimeByPosition(position)
        thisEnd = madExpObj.getExpEndDateTimeByPosition(position)
        thisSecurity = madExpObj.getSecurityByPosition(position)
        if thisSiteId == localSiteId:
            thisLocal = 1
        else:
            thisLocal = 0
        thisPI = madExpObj.getPIByPosition(position)
        if thisPI in (None, ''):
            thisPI = madInstObj.getContactName(thisInstCode)
        thisPIEmail = madExpObj.getPIEmailByPosition(position)
        if thisPIEmail in (None, ''):
            thisPIEmail = madInstObj.getContactEmail(thisInstCode)
        expDir = madExpObj.getExpDirByPosition(position)
            
        position += 1

        # some experiments set the end of the day to 24:00:00 - not
        # technically correct - reset to 23:59:59
        
        if (thisStart[3] == 24 and thisStart[4] == 0 and thisStart[5] == 0):
            thisStart[3] = 23
            thisStart[4] = 59
            thisStart[5] = 59

        if (thisEnd[3] == 24 and thisEnd[4] == 0 and thisEnd[5] == 0):
            thisEnd[3] = 23
            thisEnd[4] = 59
            thisEnd[5] = 59
        
        # apply filters
        
        # first apply instrument code filter
        if codeList[0] != 0:
            if thisInstCode not in codeList:
                continue

        # apply starttime and endtime filters
        thisStartTime = datetime.datetime(thisStart[0],
                                          thisStart[1],
                                          thisStart[2],
                                          thisStart[3],
                                          thisStart[4],
                                          thisStart[5])

        thisEndTime = datetime.datetime(thisEnd[0],
                                        thisEnd[1],
                                        thisEnd[2],
                                        thisEnd[3],
                                        thisEnd[4],
                                        thisEnd[5])
        
        if startTimeFilter != None:
            if thisEndTime < startTimeFilter:
                continue

        if endTimeFilter != None:
            if thisStartTime > endTimeFilter:
                continue

        # apply local filer
        if local == 1 and thisLocal == 0:
            continue

        # apply security filter
        if trusted == 0 and thisSecurity not in (0,2):
            continue
        
        # create exp timestamp
        if local == 1:
            thisUTTimestamp = int(os.stat(expDir).st_mtime + time.timezone)
        else:
            thisUTTimestamp = 0

        # add this experiment
        retStr += '%i,%s,%s,%i,%s,%i,%s,%i,%i,%i,%i,%i,%i,%i,%i,%i,%i,%i,%i,%i,%s,%s,%i,%i\n' % \
                (thisId,
                thisUrl,
                thisName,
                thisSiteId,
                thisSiteName,
                thisInstCode,
                thisInstName,
                thisStart[0],
                thisStart[1],
                thisStart[2],
                thisStart[3],
                thisStart[4],
                thisStart[5],
                thisEnd[0],
                thisEnd[1],
                thisEnd[2],
                thisEnd[3],
                thisEnd[4],
                thisEnd[5],
                thisLocal,
                str(thisPI),
                str(thisPIEmail),
                thisUTTimestamp,
                thisSecurity)
                
    return render(request, 'madweb/service.html', {'text': retStr})


def get_experiment_files_service(request):
    """get_experiment_files_service runs the getExperimentFilesService.py service.  
    
    Inputs:
        request/url - contains arguments:
        
            id - local experiment id
            
        Returns comma-delimited data, one line for each experiment file, with the following fields:

            1. file.name (string) Example '/opt/mdarigal/blah/mlh980120g.001'
            
            2. file.kindat (int) Kindat code.  Example: 3001
            
            3. file.kindat desc (string) Kindat description: Example 'Basic Derived Parameters'
            
            4. file.category (int) (1=default, 2=variant, 3=history, 4=real-time)
            
            5. file.status (string)('preliminary', 'final', or any other description)
            
            6. file.permission (int)  0 for public, 1 for private.  For now will not return private files.
            
            7. file DOI (string) - citable url to file
        
        Returns empty string if experiment id not found.  Skips files that are not Hdf5
    """
    id = int(request.GET['id'])
    
    # create MadrigalDB obj
    madDBObj = madrigal.metadata.MadrigalDB()

    # create MadrigalExperiments object to get full file name
    madExpObj = madrigal.metadata.MadrigalExperiment(madDBObj)

    # create Madrigal Kindat to get Kindat descriptions
    madKindatObj = madrigal.metadata.MadrigalKindat(madDBObj)
    
    madWebObj = madrigal.ui.web.MadrigalWeb(madDBObj, request)
    trusted = madWebObj.isTrusted()

        
    retStr = ''
    thisUrl = madExpObj.getExpUrlByExpId(id)
    if thisUrl is None:
        raise IOError('No such id: %i' % (id))
    expPath = madExpObj.getExpDirByExpId(id)
    kinst = madExpObj.getKinstByExpId(id)
    if os.access(os.path.join(expPath, 'fileTab.txt'), os.R_OK):
        madFileObj = madrigal.metadata.MadrigalMetaFile(madDBObj, os.path.join(expPath, 'fileTab.txt'))
        for i in range(madFileObj.getFileCount()):
            basename = madFileObj.getFilenameByPosition(i)
            name = os.path.join(expPath, basename)
            base_filename, file_extension = os.path.splitext(name)
            if file_extension not in ('.hdf5', '.hdf', '.h5'):
                continue
            kindat = madFileObj.getKindatByPosition(i)
            kindatdesc = madKindatObj.getKindatDescription(kindat, kinst)
            category = madFileObj.getCategoryByPosition(i)
            status = madFileObj.getStatusByPosition(i)
            permission = madFileObj.getAccessByPosition(i)
            doi = madFileObj.getFileDOIUrlByPosition(i)
    
            # skip private files if not trusted
            if trusted == 0 and int(permission) != 0:
                continue
                
            retStr += '%s,%i,%s,%i,%s,%i,%s\n' % \
                   (name,
                    kindat,
                    kindatdesc,
                    category,
                    status,
                    permission,
                    doi)
        
    
    
    return render(request, 'madweb/service.html', {'text': django.utils.safestring.mark_safe(retStr)})


def get_parameters_service(request):
    """get_parameters_service runs the getParametersService.py service.  
    
    Inputs:
        request/url - contains arguments:
        
            filename=<full path to data file>
            
        Returns backslash-delimited data, one for each parameter either measured or derivable, with the following fields:

            1. parameter.mnemonic (string) Example 'dti'
            
            2. parameter.description (string) Example:
                "F10.7 Multiday average observed (Ott)"
                
            3. parameter.isError (int) 1 if error parameter, 0 if not
            
            4. parameter.units (string) Example "W/m2/Hz"
            
            5. parameter.isMeasured (int) 1 if measured, 0 if derivable
            
            6. parameter.category (string) Example: "Time Related Parameter"
            
            7. parameter.isSure (int) - 1 if parameter can be found for every record, 0 if can only be found for some.
                Not relevant to Madrigal 3, where always 1
    
            8. parameter.isAddIncrement - 1 if additional increment, 0 if normal (Added in Madrigal 2.5)
                Not relevant to Madrigal 3, where always -1
    """
    filename = request.GET['filename']
    
    # create MadrigalDB obj
    madDBObj = madrigal.metadata.MadrigalDB()

    # create Madrigal File object 
    madFileObj = madrigal.data.MadrigalFile(filename, madDBObj)

    # create Madrigal Parameter object
    madParmObj = madrigal.data.MadrigalParameters(madDBObj)
    
    # create Madrigal web object 
    madWebObj = madrigal.ui.web.MadrigalWebFormat()
    

    # create lists of parameters
    measParmList = []
    derivedParmList = []
    allParmList = []
    sureParmList = []

    # use the comprehensive list of parameters to check if derivable
    parmList = madWebObj.getFormat('Comprehensive')

    # populate lists
    madFileObj.getMeasDervBothParmLists(parmList,
                                        measParmList,
                                        derivedParmList,
                                        allParmList,
                                        sureParmList)

    retStr = ''
    
    # loop through allParmList and output results
    for parm in allParmList:
        description = madParmObj.getSimpleParmDescription(parm)
        isNorm = madParmObj.getParmType(parm)
        if isNorm == 1:
            isError = 0
        else:
            isError = 1
        units = madParmObj.getParmUnits(parm)
        if parm in measParmList:
            isMeasured = 1
        else:
            isMeasured = 0
        if parm in sureParmList:
            isSure = 1
        else:
            isSure = 0
        category = madParmObj.getParmCategory(parm)
        try:
            if madParmObj.isAddIncrement(parm):
                isAddIncrement = 1
            else:
                isAddIncrement = 0
        except:
            isAddIncrement = -1
        # print out this parm
        retStr += '%s\\%s\\%i\\%s\\%i\\%s\\%i\\%i\n' % (parm,
                                                description,
                                                isError,
                                                units,
                                                isMeasured,
                                                category,
                                                isSure,
                                                isAddIncrement)
        
    return render(request, 'madweb/service.html', {'text': retStr})



def isprint_service(request):
    """isprint_service runs the isprintService.py service.  
    
    Inputs:
        request/url - contains arguments:
        
            'file': The full path to the file to be analyzed by isprint.  If over 50 MB, returns error message.
            
            'parms': Multiple separately requested parameters.
            
            'filters': Multiple of filters desired, as in isprint command
            
            'user_fullname'     user name 
            
            'user_email'        user email
            
            'user_affiliation'  user affiliation
            
            'output' - option argument specifying output file basename.  Will be Hdf5 format if extension in
                ('hdf5', 'h5', 'hdf').  Will be netCDF4 is extension is '.nc'. Otherwise ascii. If not
                given, output is ascii.
                
            'header':  t for headers, f for no header.  Defaults to no header. Ignored if not ascii output
    
    Returns data as either column delimited ascii, Hdf5, or netCDF4.
    """
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    
    # get required arguments
    thisFile = request.GET['file']
    parms = request.GET.getlist('parms')
    filters = request.GET.getlist('filters')
    filters = [f.replace('E+', 'E%2B') for f in filters]
    filters = [urllib.parse.unquote_plus(f) for f in filters]
    user_fullname = request.GET['user_fullname']
    user_email = request.GET['user_email']
    user_affiliation = request.GET['user_affiliation']
        
    # get optional arguments
    try:
        output = os.path.basename(request.GET['output'])
        filename, file_extension = os.path.splitext(output)
        if file_extension in ('.hdf5', '.h5', '.hdf'):
            format = 'Hdf5'
        elif file_extension in ('.nc',):
            format = 'netCDF4'
        else:
            format = 'ascii'
    except:
        format = 'ascii'
        output = None
        
    # verify thisFile exists, not too big
    errorMessage = None
    if not os.access(thisFile, os.R_OK):
        errorMessage = 'File %s not found' % (thisFile)
    elif os.path.getsize(thisFile) > 200.0E6:
        errorMessage = 'File %s greater than 200 MB in size - running dynamic file creation not possible.  Please use  -- download as is -- instead.' % (thisFile)
    if not errorMessage is None:
        return render(request, 'madweb/service.html', {'text': errorMessage})
    
    # make sure temporary file and directory are always deleted, even if an exception
    with tempfile.TemporaryDirectory() as tmpdirname:
                
        if not output is None:
            # we need to write to a download file
            downloadFile = os.path.join(tmpdirname, output)
            if os.access(downloadFile, os.R_OK):
                try:
                    os.remove(downloadFile)
                except:
                    pass
        try:
            header = request.GET['header']
            if header not in ('t', 'f'):
                raise ValueError('Unknown header value <%s>' % (header))
        except:
            header = 'f'
            
        # log data access
        madWebObj.logDataAccess(thisFile, user_fullname, user_email, user_affiliation)
        
        # make sure tempfile always removed
            
        # run isprint command
        cmd = '%s/bin/isprint file=%s ' % (madDB.getMadroot(), thisFile)
        if not output is None:
            cmd += 'output=%s ' % (downloadFile)
        delimiter = ' '
        cmd += delimiter.join(parms) + ' '
        filterStr = delimiter.join(filters)
        cmd += filterStr + ' '
        if format == 'ascii':
            cmd += 'summary=f '
            cmd += 'header=%s ' % (header)
            
        if output is None:
            # text response
            #result = subprocess.check_output(cmd.split())
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            result,errtext = p.communicate()
            if p.returncode != 0:
                result = errtext
            if type(result) in (bytes, numpy.bytes_):
                result = result.decode('utf-8')
            if header == 'f':
                index = result.find('\n')
                result = result[index+1:]
            return render(request, 'madweb/service.html', {'text': result})
        else:
            # file download response
            #subprocess.check_call(cmd.split())
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            result,errtext = p.communicate()
            if p.returncode != 0:
                # write the error to result file
                f = open(downloadFile, 'w')
                if type(errtext) in (bytes, numpy.bytes_):
                    errtext = errtext.decode('utf-8')
                f.write(errtext)
                f.close()
            
            f = open(downloadFile, 'rb')
            filename = os.path.basename(downloadFile)
            chunk_size = 8192
            file_type = mimetypes.guess_type(downloadFile)[0]
            if file_type is None:
                file_type = 'application/octet-stream'
            response = StreamingHttpResponse(FileWrapper(f, chunk_size),
                                             content_type=file_type)
            response['Content-Length'] = os.path.getsize(downloadFile)    
            response['Content-Disposition'] = "attachment; filename=%s" % (filename)
            os.remove(downloadFile)
            return(response)
    
    
def get_madfile_service(request):
    """get_madfile_service runs the getMadfile.cgi service.  
    
    Inputs:
        request/url - contains arguments:
        
            'fileName': The full path to the file to be downloaded as.
            
            'fileType': -1 for ascii, -2 for Hdf5, -3 for netCDF4. No other values supported
            
            'user_fullname'     user name 
            
            'user_email'        user email
            
            'user_affiliation'  user affiliation
    
    Returns file as either column delimited ascii, Hdf5, or netCDF4.
    """
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    
    # get required arguments
    fileName = request.GET['fileName']
    fileType = int(request.GET['fileType'])
    user_fullname = request.GET['user_fullname']
    user_email = request.GET['user_email']
    user_affiliation = request.GET['user_affiliation']
    
    if fileType not in (-1, -2, -3):
        return(HttpResponse('<p>fileType %i not allowed: -1 for ascii, -2 for Hdf5, -3 for netCDF4</p>' % (fileType)))
    
    # log data access
    madWebObj.logDataAccess(fileName, user_fullname, user_email, user_affiliation)

    # check filename validity
    __dirConvStr1 = '/experiments[0-9]*/[0-9][0-9][0-9][0-9]/[a-z][a-z0-9][a-z0-9]/[a-zA-Z0-9\\-_]*$'
    __dirConvStr2 = '/experiments[0-9]*/[0-9][0-9][0-9][0-9]/[a-z][a-z0-9][a-z0-9]/[0-3][0-9][a-z][a-z0-9][a-z0-9][0-9][0-9].?'
    v1 = re.search(__dirConvStr1, fileName)
    v2 = re.search(__dirConvStr2, fileName)
    endsWithH5 = fileName.endswith(".h5") or fileName.endswith(".hdf5")
    startsWithMadroot = fileName.startswith(madDB.getMadroot())

    if not(endsWithH5 and startsWithMadroot):
        # not an hdf5 file and doesn't start with madroot, invalid file
        return(HttpResponse('<p>fileName {} not allowed<p>'.format(fileName)))
        
    if not v1:
        if not v2:
            # no experiment directory found, invalid file
            return(HttpResponse('<p>fileName {} not allowed<p>').format(fileName))
        
    # make sure temporary file and directory are always deleted, even if an exception
    with tempfile.TemporaryDirectory() as tmpdirname:
    
        if fileType in (-1, -3):
            # may need to create temp file
            filepath, file_extension = os.path.splitext(fileName)
            basename = os.path.basename(filepath)
            dirname = os.path.dirname(fileName)
            if fileType == -1:
                cachedTxtFile = os.path.join(dirname, 'overview', os.path.basename(fileName) + '.txt.gz')
                tmpFile = os.path.join(tmpdirname, basename + '.txt.gz')
                if os.access(cachedTxtFile, os.R_OK):
                    # don't copy to /tmp anymore-- cached file has what we need
                    tmpFile = cachedTxtFile
                else:
                    tmpFile = os.path.join(tmpdirname, basename + '.txt')
                    madrigal.cedar.convertToText(fileName, tmpFile)
            else:
                cachedNCFile = os.path.join(dirname, 'overview', os.path.basename(fileName) + '.nc')
                tmpFile = os.path.join(tmpdirname, basename + '.nc')
                if os.access(cachedNCFile, os.R_OK):
                    # don't copy to /tmp anymore-- cached file has what we need
                    tmpFile = cachedNCFile
                else:
                    try:
                        madrigal.cedar.convertToNetCDF4(fileName, tmpFile)
                    except IOError:
                        cedarObj = madrigal.cedar.MadrigalCedarFile(fileName)
                        cedarObj.write('netCDF4', tmpFile)
            
        else:
            tmpFile = fileName
            
        f = open(tmpFile, 'rb')
        filename = os.path.basename(tmpFile)
        chunk_size = 8192
        file_type = mimetypes.guess_type(tmpFile)[0]
        if file_type is None:
            file_type = 'application/octet-stream'
        response = StreamingHttpResponse(FileWrapper(f, chunk_size),
                                         content_type=file_type)
        response['Content-Length'] = os.path.getsize(tmpFile)    
        response['Content-Disposition'] = "attachment; filename=%s" % (filename)
        if fileType in (-1, -3):
            os.remove(tmpFile)
        return(response)
        
  
def mad_calculator_service(request):
    """mad_calculator_service runs the madCalculator service.  
    
    Inputs:
        request/url - contains arguments:
        
            year, month, day, hour, min, sec 
            
            startLat - Starting geodetic latitude, -90 to 90 (float)
            
            endLat - Ending geodetic latitude, -90 to 90 (float)
            
            stepLat - Latitude step (0.1 to 90) (float)
            
            startLong - Starting geodetic longitude, -180 to 180  (float)
            
            endLong - Ending geodetic longitude, -180 to 180 (float)
            
            stepLong - Longitude step (0.1 to 180) (float)
            
            startAlt - Starting geodetic altitude, >= 0 (float)
            
            endAlt - Ending geodetic altitude, > 0 (float)
            
            stepAlt - Altitude step (>= 0.1) (float)
            
            parms - comma delimited string of Madrigal parameters desired
            
            oneD - zero or more mnemonics,float values to set input 1D values
    
    Returns comma-delimited data, one line for each combination of lat, long, and alt,
    with the following fields:

        1. latitude
        
        2. longitude
        
        3. altitude
        
        4. Values for each Madrigal parameter listed in argument parms, separated by whitespace
    """
    year = int(request.GET['year'])
    month = int(request.GET['month'])
    day = int(request.GET['day'])
    hour = int(request.GET['hour'])
    minute = int(request.GET['min'])
    second = int(request.GET['sec'])
    try:
        dt = datetime.datetime(year, month, day, hour, minute, second)
    except:
        return(HttpResponse('Illegal time: year %i, month %i, day %i, hour %i, minute %i, second %i' % (year, month, day, hour, minute, second)))
    
    startLat = float(request.GET['startLat'])
    endLat = float(request.GET['endLat'])
    if startLat == endLat:
        endLat += 0.001
    elif startLat > endLat:
        return(HttpResponse('startLat %s cannot be greater than endLat %s' % (str(startLat), str(endLat))))
    stepLat = float(request.GET['stepLat'])
    if stepLat < 0.0:
        return(HttpResponse('stepLat %s cannot be less than zero' % (str(stepLat))))
    elif stepLat == 0.0:
        stepLat = 0.001
    latList = list(numpy.arange(startLat, endLat, stepLat))
    
    startLong = float(request.GET['startLong'])
    endLong = float(request.GET['endLong'])
    if startLong == endLong:
        endLong += 0.001
    elif startLong > endLong:
        return(HttpResponse('startLong %s cannot be greater than endLong %s' % (str(startLong), str(endLong))))
    stepLong = float(request.GET['stepLong'])
    if stepLong < 0.0:
        return(HttpResponse('stepLong %s cannot be less than zero' % (str(stepLong))))
    elif stepLong == 0.0:
        stepLong = 0.001
    lonList = list(numpy.arange(startLong, endLong, stepLong))
    
    startAlt = float(request.GET['startAlt'])
    endAlt = float(request.GET['endAlt'])
    if startAlt == endAlt:
        endAlt += 0.001
    elif startAlt > endAlt:
        return(HttpResponse('startAlt %s cannot be greater than endAlt %s' % (str(startAlt), str(endAlt))))
    stepAlt = float(request.GET['stepAlt'])
    if stepAlt < 0.0:
        return(HttpResponse('stepAlt %s cannot be less than zero' % (str(stepAlt))))
    elif stepAlt == 0.0:
        stepAlt = 0.01
    altList = list(numpy.arange(startAlt, endAlt, stepAlt))
    
    # limit total calculations to 1E5
    total = len(latList) * len(lonList) * len(altList)
    if total > 1.0E5:
        return(HttpResponse('Too many points for madCalculatorService: %i' % (total)))
    
    parms = request.GET['parms']
    desiredParmList = [item.strip() for item in ['gdlat','glon','gdalt'] + parms.split(',')]
    
    oneDList = request.GET.getlist('oneD')
    oneDParmDict = {}
    for oneDStr in oneDList:
        mnem, strValue = oneDStr.split(',')
        oneDParmDict[mnem] = [float(strValue)]
    
    # capture stdout
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    madrigal.isprint.MadCalculatorGrid(None, desiredParmList, [dt], latList, lonList, altList, 
                                   oneDParmDict, summary=None)
    text = mystdout.getvalue()
    sys.stdout = old_stdout
    
    return render(request, 'madweb/service.html', {'text': text})


def mad_time_calculator_service(request):
    """mad_time_calculator_service runs the madTimeCalculator service.  Input parameters must not be location dependent
    
    Inputs:
        request/url - contains arguments:
        
            1. startyear - int 
            
            2. startmonth - int 
            
            3. startday - int
            
            4. starthour - int 
            
            5. startmin - int 
            
            6. startsec - int
            
            7. endyear - int 
            
            8. endmonth - int 
            
            9. endday - int
            
            10. endhour - int 
            
            11. endmin - int 
            
            12. endsec - int
            
            13. stephours - float - number of hours per time step
            
            14. parms - comma delimited string of Madrigal parameters desired (must not depend on location)
    
    Returns comma-delimited data, one line for each year, month, day, hour, minute, and second,
    with the following fields:

        1-6: year, month, day, hour, minute, and second
        
        2. requested parm fields
    """
    startyear = int(request.GET['startyear'])
    startmonth = int(request.GET['startmonth'])
    startday = int(request.GET['startday'])
    starthour = int(request.GET['starthour'])
    startminute = int(request.GET['startmin'])
    startsecond = int(request.GET['startsec'])
    endyear = int(request.GET['endyear'])
    endmonth = int(request.GET['endmonth'])
    endday = int(request.GET['endday'])
    endhour = int(request.GET['endhour'])
    endminute = int(request.GET['endmin'])
    endsecond = int(request.GET['endsec'])
    dt1 = datetime.datetime(startyear, startmonth, startday, starthour, startminute, startsecond)
    dt2 = datetime.datetime(endyear, endmonth, endday, endhour, endminute, endsecond)
    if dt1 > dt2:
        return(HttpResponse('End Datetime %s cannot be before start datetime %s' % (str(dt2), str(dt1))))
    
    stephours = float(request.GET['stephours'])
    if stephours <= 0.0:
        return(HttpResponse('stephours cannot be non-positive: %f' % (stephours)))
    
    dtList = []
    while dt1 <= dt2:
        dtList.append(dt1)
        dt1 += datetime.timedelta(hours=stephours)
    
    parms = request.GET['parms']
    desiredParmList = [item.strip() for item in ['year','month','day','hour','min','sec'] + parms.split(',')]
    
    # no spatial data
    latList = lonList = altList = []
    # capture stdout
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    madrigal.isprint.MadCalculatorGrid(None, desiredParmList, dtList, latList, lonList, altList, 
                                   summary=None)
    text = mystdout.getvalue()
    sys.stdout = old_stdout
    
    return render(request, 'madweb/service.html', {'text': text})




def mad_calculator2_service(request):
    """mad_calculator2_service runs the madCalculator2 service.
    
    Differs from madCalulator in that positions are a list rather than a grid.  
    
    Inputs:
        request/url - contains arguments:
        
            year, month, day, hour, min, sec 
            
            lats - comma separated list of latitudes to analyze
            
            longs - comma separated list of longitudes to analyze. Len must == len(lats)
            
            alts - comma separated list of altitudes to analyze. Len must == len(lats)
            
            parms - comma delimited string of Madrigal parameters desired
            
            oneD - zero or more mnemonics,float values to set input 1D values
                Example:  &oneD=kinst,31.0&oneD=elm,45.0
                
            twoD - zero or more mnemonics,comma-separate float list of len(lats) to set input 2D values
                Example:  twoD=te,1000,1100,1200  twoD=ti,1000,1000,1000
                          where there are 3 lats
    
    Returns comma-delimited data, one line for each lat value,
    with the following fields:

        1. latitude
        
        2. longitude
        
        3. altitude
        
        4. Values for each Madrigal parameter listed in argument parms, separated by whitespace
    """
    if request.method == 'POST':
        reqDict = request.POST
    else:
        reqDict = request.GET
    try:
        year = int(reqDict.get('year'))
    except TypeError:
        return(HttpResponse('<p>madCalculator2Service requires year</p>'))
    month = int(reqDict['month'])
    day = int(reqDict['day'])
    hour = int(reqDict['hour'])
    minute = int(reqDict['min'])
    second = int(reqDict['sec'])
    dt = datetime.datetime(year, month, day, hour, minute, second)
    
    latsStr = reqDict['lats']
    lats = [float(item) for item in latsStr.split(',')]
    longsStr = reqDict['longs']
    longs = [float(item) for item in longsStr.split(',')]
    altsStr = reqDict['alts']
    alts = [float(item) for item in altsStr.split(',')]
    
    parms = reqDict['parms']
    desiredParmList = [item.strip() for item in ['gdlat','glon','gdalt'] + parms.split(',')]
    
    oneDList = reqDict.getlist('oneD')
    oneDParmDict = {}
    for oneDStr in oneDList:
        mnem, strValue = oneDStr.split(',')
        oneDParmDict[mnem] = [float(strValue)]
        
    twoDList = reqDict.getlist('twoD')
        
    twoDParmDict = {}
    for twoDStr in twoDList:
        items = twoDStr.split(',')
        if len(items) != 1 + len(lats):
            raise ValueError('twoDstr %s not correct number of points' % (str(twoDStr)))
        mnem = items[0]
        floatValues = [float(item) for item in items[1:]]
        # now we need to expand these values to be two dimensional 1 x len(lats)
        values = numpy.zeros((1,len(lats)), dtype=float)
        values[0][:] = floatValues
        twoDParmDict[mnem] = values

    # capture stdout
    old_stdout = sys.stdout
    sys.stdout = mystdout = io.StringIO()
    madrigal.isprint.MadCalculatorList(None, desiredParmList, [dt], lats, longs, alts, 
                                       oneDParmDict, twoDParmDict, summary=None)
    text = mystdout.getvalue()
    sys.stdout = old_stdout
    
    return render(request, 'madweb/service.html', {'text': text})
    
    
    

def mad_calculator3_service(request):
    """mad_calculator3_service runs the madCalculator3 service.
    
    Differs from madCalulator in that multiple times, each with a unique list of positions, can be passed in.
    
    Inputs:
      request/url - contains arguments:
      
        year - a comma-separated list of years - (required)
        
        month  - a comma-separated list of months - (required)
        
        day - a comma-separated list of days - (required)
        
        hour - a comma-separated list of hours - (required)
        
        min - a comma-separated list of minutes - (required)
        
        sec - a comma-separated list of seconds - (required)
        
        numPos - a comma-sepatated list of the number of positions for each time - (required)
        
        lats - a comma-separated list of geodetic latitudes, -90 to 90 (required).  Listed
                  for first time, then second, etc.  Total must be equal to the sum
                  of numPos.
                  
        longs - a comma-separated list of longitudes (required) Listed
                  for first time, then second, etc.  Total must be equal to the sum
                  of numPos.
                  
        alts - a comma-separated list of geodetic altitudes in km (required) Listed
                  for first time, then second, etc.  Total must be equal to the sum
                  of numPos.
                  
        parms - comma delimited string of Madrigal parameters desired (required)
        
        oneD - string in form <parm>,<comma-separated values> This argument allows the user to
                            set any number of one-D parameters to be used in the calculation.
                            Value must be parameter name, comma, list of values as double,
                            where length of list is equal to number of times.
                            Example:  &oneD=kinst,31.0,31.0&oneD=elm,45.0,50
                            (optional - 0 or more allowed)        
                            
         twoD=<parm>,<values>  (optional - 0 or more allowed) This argument allows the user to
                            set any number of two-D parameters to be used in the calculation.
                            Value must be parameter name, comma, comma-separated values.
                            Number of values must equal the sum of numPos.  Order is
                            first time values first, then second time values, etc
                            Example:  twoD=te,1000,1100,1200,1000,1100,1200 &twoD=ti,1000,1000,1000,1000,1000,1000
                            where numPos=3,3

    Returns comma-delimited data, one line for each location.  Separate times are delimited by line

    TIME MM/DD/YYYY HH:MM:SS
    
    Data lines have the following fields:
    
    1. latitude
    
    2. longitude
    
    3. altitude
    
    4. Values for each Madrigal parameter listed in argument parms, separated by whitespace
    """
    if request.method == 'POST':
        reqDict = request.POST
    else:
        reqDict = request.GET
    try:
        yearList = [int(item) for item in reqDict.get('year').split(',')]
    except AttributeError:
        return(HttpResponse('<p>madCalculator3Service requires year</p>'))
    monthList = [int(item) for item in reqDict.get('month').split(',')]
    dayList = [int(item) for item in reqDict.get('day').split(',')]
    hourList = [int(item) for item in reqDict.get('hour').split(',')]
    minList = [int(item) for item in reqDict.get('min').split(',')]
    secList = [int(item) for item in reqDict.get('sec').split(',')]
    dtList = [datetime.datetime(yearList[i], monthList[i], dayList[i],
                                hourList[i], minList[i], secList[i]) for i in range(len(yearList))]
    numPosStr = reqDict['numPos']
    numPosList = [int(item) for item in numPosStr.split(',')]
    totalPos = 0
    for numPos in numPosList:
        totalPos += numPos
    latsStr = reqDict['lats']
    lats = [float(item) for item in latsStr.split(',')]
    if len(lats) != totalPos:
        return(HttpResponse('wrong number of lats, expected %i' % (totalPos)))
    longsStr = reqDict['longs']
    longs = [float(item) for item in longsStr.split(',')]
    if len(longs) != totalPos:
        return(HttpResponse('wrong number of longs, expected %i' % (totalPos)))
    altsStr = reqDict['alts']
    alts = [float(item) for item in altsStr.split(',')]
    if len(alts) != totalPos:
        return(HttpResponse('wrong number of alts, expected %i' % (totalPos)))
    
    parms = reqDict['parms']
    desiredParmList = [item.strip() for item in ['gdlat','glon','gdalt'] + parms.split(',')]
    
    oneDList = reqDict.getlist('oneD')
    twoDList = reqDict.getlist('twoD')
    
    # since the positions can change with each call, we need to call madrigal.isprint.MadCalculatorGrid once for each time
    startIndex = 0
    endIndex = 0
    fullText = ''
    for timeIndex, numPos in enumerate(numPosList):
        startIndex = endIndex
        endIndex += numPos
        thisLats = lats[startIndex:endIndex]
        thisLongs = longs[startIndex:endIndex]
        thisAlts = alts[startIndex:endIndex]
    
        oneDParmDict = {}
        for oneDStr in oneDList:
            values = oneDStr.split(',')
            if len(values) != 1+len(dtList):
                return(HttpResponse('wrong number of values given for 1D parm %s' % (values[0])))
            oneDParmDict[values[0]] = [float(values[timeIndex+1])]
        
        twoDParmDict = {}
        
        for twoDStr in twoDList:
            values = twoDStr.split(',')
            if len(values) != 1 + totalPos:
                return(HttpResponse('twoDstr %s not correct number of points' % (str(twoDStr))))
            mnem = values[0]
            floatValues = [float(item) for item in values[1+startIndex:1+endIndex]]
            # now we need to expand these values to be two dimensional - 1,len(thisLats)
            values2D = numpy.zeros((1,len(thisLats)), dtype=float)
            values2D[0][:] = floatValues
            twoDParmDict[mnem] = values2D
            
            
    
        # capture stdout
        old_stdout = sys.stdout
        sys.stdout = mystdout = io.StringIO()
        madrigal.isprint.MadCalculatorList(None, desiredParmList, [dtList[timeIndex]], thisLats, 
                                           thisLongs, thisAlts, 
                                           oneDParmDict, twoDParmDict, summary=None)
        text = mystdout.getvalue()
        sys.stdout = old_stdout
        
        fullText += 'TIME %s\n' % (dtList[timeIndex].strftime('%m/%d/%Y %H:%M:%S'))
        fullText += text
    
    return render(request, 'madweb/service.html', {'text': fullText})
    
    
    
def geodetic_to_radar_service(request):
    """geodetic_to_radar_service runs the geodeticToRadar service.
    
    Inputs:
      request/url - contains arguments:
      
        slatgd  - radar geodetic latitude
        
        slon - radar longitude
        
        saltgd - radar geodetic altitude
        
        gdlat - a comma-separated list of geodetic latitude of point
        
        glon - a comma-separated list of longitude of point. Len must be same as gdlat
        
        gdalt - a comma-separated list of geodetic altitude of point. Len must be same as gdlat


    Returns comma-delimited data, one line for point in lists (points treated as individual combinations, not grids):

        1. radar azimuth in degrees (0 = north)
        
        2. radar elevation in degrees 
        
        3. radar range in km
    """
    slatgd = float(request.GET['slatgd'])
    slon = float(request.GET['slon'])
    saltgd = float(request.GET['saltgd'])
    oneDParmDict = {'GDLATR': [slatgd],
                    'GDLONR': [slon],
                    'GALTR': [saltgd]}
    gdlatStr = request.GET['gdlat']
    gdlatList = [float(item) for item in gdlatStr.split(',')]
    glonStr = request.GET['glon']
    glonList = [float(item) for item in glonStr.split(',')]
    gdaltStr = request.GET['gdalt']
    gdaltList = [float(item) for item in gdaltStr.split(',')]
    desiredParmList = ['azm', 'elm', 'range']
    dtList = [datetime.datetime(2001,1,1)] # not relevant
    if len(gdlatList) != len(glonList) or len(gdlatList) != len(gdaltList):
        return(HttpResponse('all point list lengths must be equal'))
    
    fullText = ''
    
    delimiter = ','
    for i in range(len(gdlatList)):
         # capture stdout
        old_stdout = sys.stdout
        sys.stdout = mystdout = io.StringIO()
        madrigal.isprint.MadCalculatorGrid(None, desiredParmList, dtList, [gdlatList[i]], 
                                       [glonList[i]], [gdaltList[i]], summary=None,
                                       oneDParmDict=oneDParmDict)
        text = mystdout.getvalue()
        sys.stdout = old_stdout
        for line in text.split('\n'):
            items = line.split()
            fullText += delimiter.join(items) + '\n'
    
    return render(request, 'madweb/service.html', {'text': fullText})


def radar_to_geodetic_service(request):
    """radar_to_geodetic_service runs the radarToGeodetic service.
    
    Inputs:
      request/url - contains arguments:
      
        slatgd  - radar geodetic latitude
        
        slon - radar longitude
        
        saltgd - radar geodetic altitude
        
        azs - a comma-separated list of azimuths of point
        
        els - a comma-separated list of elevations of point. Len must be same as azs
        
        ranges - a comma-separated list of ranges to point. Len must be same as azs


    Returns comma-delimited data, one line for point in lists  (points treated as individual combinations, not grids):

        1. geodetic latitude
        
        2. longitude (-180 to 180)
        
        3. geodetic altitude in km
    """
    slatgd = float(request.GET['slatgd'])
    slon = float(request.GET['slon'])
    saltgd = float(request.GET['saltgd'])
    azStr = request.GET['az']
    azList = [float(item) for item in azStr.split(',')]
    elStr = request.GET['el']
    elList = [float(item) for item in elStr.split(',')]
    rangeStr = request.GET['range']
    rangeList = [float(item) for item in rangeStr.split(',')]
    if len(azList) != len(elList) or len(azList) != len(rangeList):
        return(HttpResponse('all point list lengths must be equal'))
    
    fullText = ''
    
    for i in range(len(azList)):
        gdlat,glon,gdalt = madrigal._derive.radarToGeodetic(slatgd, slon, saltgd,
                                                            azList[i], elList[i], rangeList[i])
        fullText += '%f,%f,%f\n' % (gdlat,glon,gdalt)
        
    return render(request, 'madweb/service.html', {'text': fullText})
    
    

def list_file_times_service(request):
    """list_file_times_service runs the listFileTimes service.
    
    Inputs:
      request/url - contains arguments:
      
        Optional: expDir - experiment directory to list.  Can be absolute or relative to
            experiments[0-9]*. Default is all files in $MADROOT/experiments*

    Returns comma-delimited data, one for each file:
    
        1. Full path of file
        
        2. File modification time in form YYYY-MM-DD HH:MM:SS (UT time)
    """
    expDir = None
    try:
        expDir = request.GET['expDir']
    except:
        pass
    madDB = madrigal.metadata.MadrigalDB()
    fileList = madDB.listFileTimes(expDir)
    fullText = '\n\n'
    for filename, filetime in fileList:
        fullText += "\'%s\', %s\n" % (filename, filetime.strftime('%Y-%m-%d %H:%M:%S'))
        
    return render(request, 'madweb/service.html', {'text': django.utils.safestring.mark_safe(fullText)})


def download_web_file_service(request):
    """download_web_file_service runs the downloadWebFile service.
    
    Inputs:
      request/url - contains arguments:
      
        expPath - path to file starting at experiments*

    Returns comma-delimited data, one for each file:
    
        1. Full path of file
        
        2. File modification time in form YYYY-MM-DD HH:MM:SS (UT time)
    """
    expPath = request.GET['expPath']
    madDB = madrigal.metadata.MadrigalDB()
    downloadFile = os.path.join(madDB.getMadroot(), expPath)
    f = open(downloadFile, 'rb')
    thisFile = django.core.files.File(f)
    response = HttpResponse(thisFile, content_type='application/x-octet-stream')
    response['Content-Disposition'] = 'attachment; filename="' + os.path.basename(downloadFile) + '"'
    response['Content-Length'] = os.path.getsize(downloadFile)
    return(response)


def trace_magnetic_field_service(request):
    """trace_magnetic_field_service runs the traceMagneticField service.
    
    Inputs:
      request/url - contains arguments:
      
        year, month, day, hour, min, sec
        
        inputType (0 for geodetic, 1 for GSM)
        
        outputType (0 for geodetic, 1 for GSM)
        
            The following parameter depend on inputType:
            
        in1 - a comma-separated list of geodetic altitudes or ZGSMs of starting point
        
        in2 - a comma-separated list of geodetic latitudes or XGSMs of starting point
        
        in3 - a comma-separated list of longitude or YGSM of starting point

            Length of all three lists must be the same
        
        model - 0 for Tsyganenko, 1 for IGRF
        
        qualifier - 0 for conjugate, 1 for north_alt, 2 for south_alt, 3 for apex, 4 for GSM XY plane
        
        stopAlt - altitude in km to stop trace at, if qualifier is north_alt or south_alt.
        
        If other qualifier, this parameter is not required.

    Returns comma-delimited data, one line for point in in lists:

        1. geodetic altitude or ZGSM of ending point
        
        2. geodetic latitude or XGSM of ending point
        
        3. longitude or YGSM of ending point
    """
    year = int(request.GET['year'])
    month = int(request.GET['month'])
    day = int(request.GET['day'])
    hour = int(request.GET['hour'])
    minute = int(request.GET['min'])
    second = int(request.GET['sec'])
    dt = datetime.datetime(year, month, day, hour, minute, second)
    inputType = int(request.GET['inputType'])
    if inputType not in (0,1):
        return(HttpResponse('inputType must be 0 or 1, not %i' % (inputType)))
    outputType = int(request.GET['outputType'])
    if outputType not in (0,1):
        return(HttpResponse('outputType must be 0 or 1, not %i' % (outputType)))
    in1Str = request.GET['in1']
    in1List = [float(item) for item in in1Str.split(',')]
    in2Str = request.GET['in2']
    in2List = [float(item) for item in in2Str.split(',')]
    in3Str = request.GET['in3']
    in3List = [float(item) for item in in3Str.split(',')]
    if len(in1List) != len(in2List) or len(in1List) != len(in3List):
        return(HttpResponse('All three in* lists must have same length'))
    model = int(request.GET['model'])
    if model not in (0,1):
        return(HttpResponse('model must be 0 or 1, not %i' % (model)))
    qualifier = int(request.GET['qualifier'])
    if qualifier not in (0,1,2,3,4):
        return(HttpResponse('model must be in 0,1,2,3,4 not %i' % (model)))
    try:
        stopAlt = float(request.GET['stopAlt'])
    except:
        stopAlt = 0.0
        
    fullText = ''
    resultArr = numpy.zeros((3,), dtype='f8')
    madDB = madrigal.metadata.MadrigalDB()
    madDeriveObj = madrigal.derivation.MadrigalDerivationMethods(madDB.getMadroot())
    for i in range(len(in1List)):
        madDeriveObj.traceMagneticField(year, month, day, hour, minute, second, 
                                        inputType, outputType, in1List[i], in2List[i], in3List[i], 
                                        model, qualifier, stopAlt, resultArr)
        fullText += '%f,%f,%f\n' % (resultArr[0], resultArr[1], resultArr[2])

    return render(request, 'madweb/service.html', {'text': fullText})


def global_file_search_service(request):
    """global_file_search_service returns a list of full paths to files or citable urls based on search arguments
    
    Inputs:
        request/url - contains arguments:
        
            startDate: start date in form YYYY-MM-DD to filter experiments before
            endDate: end date in form YYYY-MM-DD to filter experiments after 
            inst: (optional, multiple allowed) an instrument code or name. For names,
                fnmatch will be used. If not set, all instruments used. 
            kindat: (optional, multiple allowed) a kind of data codes or name. For names,
                fnmatch will be used. If not set, all kinds of data used.
            seasonalStartDate: (optional) in form MM/DD, rejects all days earlier in year. If not set
                implies 01/01
            seasonalEndDate: (optional) in form MM/DD, rejects all days later in year. If not set
                implies 12/31
            includeNonDefault: (optional) if "True", include realtime files when there are no default. 
                If not set, only default files.
            expName: (optional)  - filter experiments by the experiment name.  fnmatch rules
                If not set, no filtering by experiment name.
            excludeExpName: (optional)  - exclude experiments by the experiment name.  fnmatch rules  
                If not set, no excluding experiments by experiment name.
            fileDesc: (optional) filter files using input file Description string via fnmatch. 
                If not set, in no filtering by file name
            returnCitation: (optional) if True, return a list of file citations.  If not set, return
                a list of full paths to the files selected
    
    """
    madDB = madrigal.metadata.MadrigalDB()
    madWebObj = madrigal.ui.web.MadrigalWeb(madDB, request)
    
    # get required arguments
    startDate = request.GET['startDate']
    endDate = request.GET['endDate']
    startDate = datetime.datetime.strptime(startDate, '%Y-%m-%d')
    endDate = datetime.datetime.strptime(endDate, '%Y-%m-%d')
        
    # get optional arguments
    inst = request.GET.getlist('inst')
    if inst == []:
        inst = None
    kindat = request.GET.getlist('kindat')
    if kindat == []:
        kindat = None
    seasonalStartDate = request.GET.get('seasonalStartDate', default = None)
    seasonalEndDate = request.GET.get('seasonalEndDate', default = None)
    includeNonDefault = bool(request.GET.get('includeNonDefault', default = False))
    expName = request.GET.get('expName', default = None)
    excludeExpName = request.GET.get('excludeExpName', default = None)
    fileDesc = request.GET.get('fileDesc', default = None)
    returnCitation = bool(request.GET.get('returnCitation', default = False))
    
    result = madWebObj.global_file_search(startDate, endDate, inst, kindat, 
                                          seasonalStartDate, seasonalEndDate, 
                                          includeNonDefault, expName, excludeExpName, 
                                          fileDesc, returnCitation)
    
    fullText = ''
    for item in result:
        fullText += '%s\n' % (item)
    
    return render(request, 'madweb/service.html', {'text': django.utils.safestring.mark_safe(fullText)})
    
    


def get_url_list_from_group_id_service(request):
    """get_url_list_from_group_id_service returns a list of citable urls associated with group id.  
    
    Inputs:
        request/url - contains arguments:
        
            id - group id
            
        Returns one line for each citable url
        
        Returns empty string if experiment id not found.  Skips files that are not Hdf5
    """
    id = int(request.GET['id'])
    
    # create MadrigalDB obj
    madDBObj = madrigal.metadata.MadrigalDB()

    urlList = madDBObj.getListFromGroupId(id)
        
    retStr = ''
    for url in urlList:
        retStr += '%s\n' % (url)
    
    return render(request, 'madweb/service.html', {'text': django.utils.safestring.mark_safe(retStr)})


def set_group_id_from_url_list_service(request):
    """set_group_id_from_url_list sets a list of citable urls to a group id .  
    
    Inputs:
        request/url - contains arguments:
            
            'user_fullname'     user name 
            
            'user_email'        user email
            
            'user_affiliation'  user affiliation
            
            'url' -  citable url.  Multiple arguments allowed
    
    Returns group id (integer) set
    """
    madDB = madrigal.metadata.MadrigalDB()
    
    print(request.GET)
    
    # get required arguments
    urls = request.GET.getlist('url')
    user_fullname = request.GET['user_fullname']
    user_email = request.GET['user_email']
    user_affiliation = request.GET['user_affiliation']
    
    id = madDB.createGroupIdWithList(user_fullname, user_email, user_affiliation, urls)
    
    return render(request, 'madweb/service.html', {'text': str(id)})


### doc pages ###

def docs(request, name):
    madDB = madrigal.metadata.MadrigalDB()
    openMadObj = madrigal.openmadrigal.OpenMadrigal(madDB)
    bg_color = madDB.getBackgroundColor()
    if name.find('..') != -1:
        # no trying to look elsewhere
        return(HttpResponse('Illegal name passed to docs: <%s>' % (name)))
    # check if siteSpecitic.html 
    siteSpecificPath = os.path.join(madDB.getMadroot(), 'source/madpy/djangoMad/madweb/templates/madweb/siteSpecific.html')
    if os.access(siteSpecificPath, os.R_OK):
        siteSpecific = reverse('docs', args=['siteSpecific.html'])
    else:
        siteSpecific = '#'
    openmadrigal = openMadObj.getOpenMadrigalUrl()
    # since google insists filenames are case insensitive, convert to right name if there is no direct match if possible
    this_file = os.path.join(madDB.getMadroot(), 'source/madpy/djangoMad/madweb/templates/madweb', name)
    if not os.access(this_file, os.R_OK):
        found = False
        existing_files = glob.glob(os.path.join(madDB.getMadroot(), 'source/madpy/djangoMad/madweb/templates/madweb/*.html'))
        for existing_file in existing_files:
            if name.lower() == os.path.basename(existing_file).lower():
                name = os.path.basename(existing_file)
                found = True
                break # correct name found and name modified
        if not found:
            return(HttpResponse('<p>Cannot find %s</p>' % (str(name))))
        
    if os.path.isdir(this_file):
        return(HttpResponse('<p>%s is a directory</p>' % (str(name))))
                                   
    return render(request, 'madweb/%s' % (name), {'bg_color': bg_color, 'siteSpecific': siteSpecific,
                                                     'openmadrigal': openmadrigal})

    