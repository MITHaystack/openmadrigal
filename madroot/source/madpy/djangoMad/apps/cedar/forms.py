"""Forms for cedar application

$Id: forms.py 7033 2019-10-03 20:15:55Z brideout $
"""

# standard python imports
import os.path
import datetime

# django imports
import django.forms
import django.utils.html
import django.utils.safestring

# Madrigal imports
import madrigal.metadata
import madrigal.ui.userData



class AdminLogForm(django.forms.Form):
    """AdminLogForm is a Form class for the get log admin interface
    """
    def __init__(self, *args, **kwargs):
        # Extract the request object passed from the view
        request = kwargs.pop('request', None)
        super(AdminLogForm, self).__init__(*args, **kwargs)
        
        # The admin identity is supplied by the user_fullname cookie.
        self.user_fullname = request.COOKIES.get('user_fullname') if request else None
        
        selectedSite = None
        kinstChoices = [('0', 'Select a site first'),]
        if len(args) > 0:
            try:
                if 'site' in args[0]:
                    selectedSite = int(args[0]['site'])
            except:
                pass
        
        madDB = madrigal.metadata.MadrigalDB()
        madSiteObj = madrigal.metadata.MadrigalSite(madDB)
        madInstObj = madrigal.metadata.MadrigalInstrument(madDB)
        self.madUserObj = madrigal.ui.userData.MadrigalUserData(madDB)
        
        madExpObj = madrigal.metadata.MadrigalExperiment(madDB, os.path.join(madDB.getMadroot(), 'metadata/expTabAll.txt'))
        siteDict = {} # temp dict with key = siteId, value = list of kinst where there is data at that site
        for i in range(madExpObj.getExpCount()):
            siteId = madExpObj.getExpSiteIdByPosition(i)
            kinst = madExpObj.getKinstByPosition(i)
            try:
                if kinst in siteDict[siteId]:
                    continue
            except KeyError:
                pass
            expUrl = madExpObj.getExpUrlByPosition(i)
            if madDB.isTestExperiment(expUrl):
                continue
            if siteId in siteDict:
                siteDict[siteId].append(kinst)
            else:
                siteDict[siteId] = [kinst]
                
        # make siteList, which is sorted list of (siteid, kinst, instName) and siteChoices
        # which is (siteID, siteName)
        self.siteList = []
        self.siteChoices = [("0", "Select your site")]
        sites = list(siteDict.keys())
        sites.sort()
        for site in sites:
            if site not in (10,): #skip CEDAR site
                self.siteChoices.append((site, madSiteObj.getSiteName(site)))
            kinstList = siteDict[site]
            kinstList.sort()
            for kinst in kinstList:
                self.siteList.append((site, kinst, madInstObj.getInstrumentName(kinst)))
                if not selectedSite is None:
                    if selectedSite == site:
                        kinstChoices.append((kinst, madInstObj.getInstrumentName(kinst)))
            
        # now add to self.siteList and self.siteChoices from hostSite.txt file
        filename = os.path.join(madDB.getMadroot(), 'metadata/hostSite.txt')
        f = open(filename)
        
        lines = f.readlines()
        for line in lines:
            items = line.strip().split(',')
            if len(items) < 3:
                continue
            siteId = int(items[0])
            # check this is unique siteId
            if siteId in siteDict:
                raise IOError('File hostSite.txt has siteId %i from siteTab.txt' % (siteId))
            kinstList = []
            for item in items[2:]:
                kinst = int(item)
                kinstList.append(kinst)
                self.siteList.append((siteId, kinst, madInstObj.getInstrumentName(kinst)))
                if not selectedSite is None:
                    if selectedSite == siteId:
                        kinstChoices.append((kinst, madInstObj.getInstrumentName(kinst)))
            self.siteChoices.append((str(siteId), items[1]))
            
        self.fields['site'] = django.forms.ChoiceField(widget = django.forms.Select(attrs={"onChange":'selectSite(this.form)'}),
                                                       choices=self.siteChoices, 
                                                       initial='0')
        
        self.fields['password'] = django.forms.CharField(widget = django.forms.PasswordInput())
        
        self.fields['kinst'] = django.forms.CharField(widget=django.forms.SelectMultiple(choices=kinstChoices))
        
        # time selection
        self.fields['startDate'] = django.forms.DateField(input_formats=['%Y-%m-%d'],
                                                          initial=datetime.datetime(2011,1,1,0,0,0))
        now = datetime.datetime.now()
        self.fields['endDate'] = django.forms.DateField(input_formats=['%Y-%m-%d'],
                                                        initial=datetime.datetime(now.year,12,31,0,0,0))
        
        
    def clean(self):
        
        """clean verifies password
        """
        siteId = int(self.cleaned_data['site'])
        siteName = None
        for id, name in self.siteChoices:
            if int(id) == siteId:
                siteName = name
                break
        if siteName is None:
            raise django.forms.ValidationError('Illegal site choosen')
        if not self.user_fullname:
            raise django.forms.ValidationError('Missing user_fullname cookie')
        if not self.madUserObj.verifyUser(self.user_fullname, self.cleaned_data['password']):
            raise django.forms.ValidationError('Incorrect password')
        
        
        
