"""testCitationWebServices.py is a script to test writing citations.  Since citations are meant
to be permanent at cedar.openmadrigal.org, this script must be run on a test server only.

$Id: testCitationWebServices.py 7539 2023-06-01 17:56:42Z brideout $
"""

usage = 'python testCitationWebServices.py <local_server_url>'

# standard python imports
import os, os.path, sys
import traceback, datetime

# Madrigal imports
import madrigalWeb.madrigalWeb

if len(sys.argv) != 2:
    print(usage)
    sys.exit(0)
    
# constants
user_fullname = 'Bill Rideout - automated test'
user_email = 'brideout@mit.edu'
user_affiliation = 'MIT Haystack'

baseUrl = sys.argv[1]

if baseUrl.find('cedar.openmadrigal') != -1:
    raise ValueError('Cannot use cedar.openmadrigal for testing - use test site instead')
    
testData = madrigalWeb.madrigalWeb.MadrigalData(baseUrl)

success = True

print('Test of getCitationListFromFilters')
try:
    startDate = datetime.datetime(1998,1,1)
    endDate = datetime.datetime(1998,2,1)
    inst = ['Millstone*', 'Jicamarca*']
    result = testData.getCitationListFromFilters(startDate, endDate, inst)
    print(result)
    print('')
except:
    traceback.print_exc()
    print('Test of createCitationGroupFromList failed')
    success = False
    
print('Test of createCitationGroupFromList')
try:
    result = testData.createCitationGroupFromList(result, user_fullname, user_email, user_affiliation, useLocal=True)
    print(result)
    print('')
except:
    traceback.print_exc()
    print('Test of createCitationGroupFromList failed')
    success = False

print('Test of getCitedFilesFromUrl')
url = os.path.join(baseUrl, 'getCitationGroup?id=1001')
try:
    result = testData.getCitedFilesFromUrl(url)
    print(result)
    print('')
except:
    traceback.print_exc()
    print('Test of getCitedFilesFromUrl failed')
    success = False
    
if success:
    print('Success')
else:
    print('Failure')
    
