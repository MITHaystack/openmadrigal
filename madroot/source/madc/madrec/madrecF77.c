/* $Id: madrecF77.c 3304 2011-01-17 15:25:59Z brideout $ */

/*

Fortran callable C routines for Fortran access to the C-language
Madrigal API - madrec module.
________________________________________________________________________

INTEGER FUNCTION MDOPEN(IOTYPE, FILEC)
   INTEGER IOTYPE
   CHARACTER FILEC(128)
C
   Opens CEDAR file for sequential reading or writing.
C
   IOTYPE -  file type as described below
       Open Cedar file for sequential reading:
             1 - Determine file type automatically
            10 - Madrigal file
            11 - Blocked Binary file
            12 - Cbf file
            13 - Unblocked Binary file
            14 - Ascii file
       Create Cedar file for update; discard previous contents
          if any:
             2 - Madrigal file
            20 - Madrigal file
            21 - Blocked Binary file
            22 - Cbf file
            23 - Unblocked Binary file
            24 - Ascii file
       Create Cedar file in memory for sequential and random read and write. 
            30 - Determine file type automatically
            40 - Madrigal file
            41 - Blocked Binary file
            42 - Cbf file
            43 - Unblocked Binary file
            44 - Ascii file 
       Fast create Cedar file in memory for sequential and random read and write.
          Does not calculate min and and max parameter values 
            50 - Determine file type automatically
            60 - Madrigal file
            61 - Blocked Binary file
            62 - Cbf file
            63 - Unblocked Binary file
            64 - Ascii file
            
   FILEC - file name
C
   Returns file handle (0-9) or negative value if file cannot be opened.
   Call MDGERR to get error description. At most 10 files can be open
   simultaneously.
________________________________________________________________________

INTEGER FUNCTION MDCLOS(MADFIL)
  INTEGER MADFIL

     Closes CEDAR file.

  MADFIL - File handle

  Returns: 0 - File closed successfully
           1 - Error closing file
           2 - File not open
           3 - Error flushing file
________________________________________________________________________

INTEGER FUNCTION MDREAD(MADFIL)
  INTEGER MADFIL

  Reads next CEDAR record

  MADFIL - File handle

  Returns: 0 - Record read successfully
           1 - Illegal file type
          -n - Error
________________________________________________________________________

INTEGER FUNCTION MDWRIT(MADFIL)
  INTEGER MADFIL

  Writes next Madrigal record

  MADFIL - File handle

  Returns: 0 - Record written successfully
           1 - Illegal file type
          -n - Error
          
________________________________________________________________________

INTEGER FUNCTION REWIND(MADFIL)
  INTEGER MADFIL

  Resets a file in memory to point to first record

  MADFIL - File handle

  Returns: 0 - Success
           1 - Illegal file type
          -n - Error
          
________________________________________________________________________

INTEGER FUNCTION GRECNO(MADFIL, RECNO)
  INTEGER MADFIL
  INTEGER RECNO

  Finds a given record number in a file (GRECNO stands for
  Get record by record number)

  MADFIL - File handle
  RECNO  - Record number (1 <= RECNO <= Total number of records)

  Returns: 0 - Success
          -1 - Specified record not in file

________________________________________________________________________

INTEGER FUNCTION GRCKEY(MADFIL, KEY)
  INTEGER MADFIL
  DOUBLE PRECISION KEY

  Finds a given record number in a file using the time key
  The record is the first data record for which key is
  greater than or equal to the start key of the
  record, and less than the start time of the
  following record. Thus, if the specified key
  corresponds to a time within a record, the
  first such record is returned. Header or catalog
  records are never returned. (GRCKEY stands for
  Get record by key)

  MADFIL - File handle
  KEY  - time in seconds since 1/1/1950

  Returns: 0 - Success
          -1 - Specified record not in file

_________________________________________________________________

INTEGER FUNCTION MDCOPY(MADFL1, MADFL2)
  INTEGER MADFL1
  INTEGER MADFL2

  Copies a record from one file to another

  MADFL1 - File handle of source record
  MADFL2 - File handle of destination record

  Returns: 0 - Success
           1 - Failure
________________________________________________________________________

INTEGER FUNCTION MDISDR(MADFIL)
  INTEGER MADFIL

  Identifies data records

  MADFIL - File handle

  Returns: 0 - Current record is not a data record
           1 - Current record is a data record
           
________________________________________________________________________

DOUBLE PECISION FUNCTION GTPMIN(MADFIL, PARCOD)
  INTEGER MADFIL
  INTEGER PARCOD

  Returns minimum value in file of given parcode

  MADFIL - File handle
  PARCOD - Parameter code

  Returns: Scaled minimum parameter value.  File must
  be opened in memory (types 30-44).  If not found,
  returns missing (1E-38).  Data rows with all error
  parameters invalid are not counted.
  
  
________________________________________________________________________

DOUBLE PECISION FUNCTION GTPMAX(MADFIL, PARCOD)
  INTEGER MADFIL
  INTEGER PARCOD

  Returns maximum value in file of given parcode

  MADFIL - File handle
  PARCOD - Parameter code

  Returns: Scaled maximum parameter value.  File must
  be opened in memory (types 30-44)  If not found,
  returns missing (1E-38).  Data rows with all error
  parameters invalid are not counted.

________________________________________________________________________

SUBROUTINE MDCREA(MADFIL,
            LPROL, JPAR, MPAR, NROW,
            KREC, KINST, KINDAT,
            YEAR1, MONTH1, DAY1,
            HOUR1, MIN1, SEC1, CSEC1,
            YEAR2, MONTH2, DAY2,
            HOUR2, MIN2, SEC2, CSEC2)    
  MADFIL - File handle
  INTEGER MADFIL,LPROL, JPAR, MPAR, NROW,KREC, KINST, KINDAT,
          YEAR1, MONTH1, DAY1, HOUR1, MIN1, SEC1, CSEC1,
          YEAR2, MONTH2, DAY2, HOUR2, MIN2, SEC2, CSEC2

    Creates a madrigal record with the specified size and prolog. The
    1d and 2d parameters must be inserted later by calls to
    MDS1DP and MDS2DP.

       MADFIL - File handle
       LPROL   - Length of prolog
       JPAR    - Number of parameters in 1d array
       MPAR    - Number of parameters in 2d array
       NROW    - Number of rows in 2d array
       KREC    - Kind of record
       KINST   - Instrument code
       KINDAT  - Kind-of-data code
       YEAR1-CSEC1 - Start date and time
       YEAR2-CSEC2 - End date and time
________________________________________________________________________


SUBROUTINE MDG1DP(MADFIL, PARCOD, PARM)
  INTEGER MADFIL, PARCOD
  DOUBLE PRECISION PARM

  Gets a 1d parameter from the current record.

  MADFIL - File handle
  PARCOD - Parameter code
  PARM    - Parameter value
________________________________________________________________________

INTEGER FUNCTION MDGNRW(MADFIL) {
  INTEGER MADFIL

  Gets number of rows in 2d array.

  MADFIL - File handle

  Returns: Number of rows in 2d array.
________________________________________________________________________

INTEGER FUNCTION MDGKST(MADFIL) {
  INTEGER MADFIL

  Gets Kind of instrument (Kinst) integer.
  MDGKST stands for MaDrec Get KinST

  MADFIL - File handle

  Returns: Kind of instrument (Kinst) integer.
  
________________________________________________________________________

INTEGER FUNCTION MDGKDT(MADFIL) {
  INTEGER MADFIL

  Gets Kind of data (Kindat) integer.
  MDGKDT stands for MaDrec Get Kind of DaTa

  MADFIL - File handle

  Returns: Kind of data (Kindat) integer.
________________________________________________________________________

INTEGER FUNCTION MDIBYR(MADFIL) {
  INTEGER MADFIL

  Gets beginning year integer.

  MADFIL - File handle

  Returns: beginning year integer.
________________________________________________________________________

INTEGER FUNCTION MDIBDT(MADFIL) {
  INTEGER MADFIL

  Gets beginning date (MMDD) integer.

  MADFIL - File handle

  Returns: beginning date (MMDD) integer.
________________________________________________________________________

INTEGER FUNCTION MDIBHM(MADFIL) {
  INTEGER MADFIL

  Gets beginning hour/minute IBHM (HHMM) integer.

  MADFIL - File handle

  Returns: beginning hour/minute (HHMM) integer.
________________________________________________________________________


INTEGER FUNCTION MDIBCS(MADFIL) {
  INTEGER MADFIL

  Gets beginning second/centisecond IBCS (SSCC) integer.

  MADFIL - File handle

  Returns: beginning second/centisecond (SSCC) integer.
________________________________________________________________________


INTEGER FUNCTION MDIEYR(MADFIL) {
  INTEGER MADFIL

  Gets ending year integer.

  MADFIL - File handle

  Returns: ending year integer.
________________________________________________________________________

INTEGER FUNCTION MDIEDT(MADFIL) {
  INTEGER MADFIL

  Gets ending date (MMDD) integer.

  MADFIL - File handle

  Returns: ending date (MMDD) integer.
________________________________________________________________________

INTEGER FUNCTION MDIEHM(MADFIL) {
  INTEGER MADFIL

  Gets ending hour/minute IEHM (HHMM) integer.

  MADFIL - File handle

  Returns: ending hour/minute (HHMM) integer.
________________________________________________________________________


INTEGER FUNCTION MDIECS(MADFIL) {
  INTEGER MADFIL

  Gets ending second/centisecond IESC (SSCC) integer.

  MADFIL - File handle

  Returns: ending second/centisecond (SSCC) integer.
________________________________________________________________________


SUBROUTINE MDG2DP(MADFIL, PARCOD, PARM)
  INTEGER MADFIL, PARCOD
  DOUBLE PRECISION PARM(NRANMX)

  Gets a 2d parameter from the current record.

  MADFIL - File handle
  PARCOD - Parameter code
  PARM    - Parameter value array
________________________________________________________________________

SUBROUTINE MDGFLT(MADFIL, PARCOD, PARM)
  INTEGER MADFIL, PARCOD
  DOUBLE PRECISION PARM(NRANMX)

  Gets a flattened parameter from the current record. If its
  a 1D parameter, its value is copied into the first NROW
  doubles in PARM array.  If its a 2D parameter, it acts just
  like MDG2DP.  With this method all parameters act like 2D
  parameters.
  
  Stands for MaDrigal Get FLaTtened parameter

  MADFIL - File handle
  PARCOD - Parameter code (can be 1D or 2D)
  PARM    - Parameter value array
________________________________________________________________________

SUBROUTINE MDS1DP(MADFIL, PARCOD, PARM, INDEX)
  INTEGER MADFIL, PARCOD, INDEX
  DOUBLE PRECISION PARM

  Sets 1d parameter

  MADFIL - File handle
  PARCOD - Parameter code
  PARM    - Parameter value
  INDEX   - Position of parameter in 1d array (1<=INDEX<=JPAR)
  
  Note: to set special value missing, use PARM=1.e-38.
      To set special value assumed (for error parms only), use PARM=2.e-38
      To set special value knownbad (for error parms only), use PARM=3.e-38
________________________________________________________________________

SUBROUTINE MDS2DP(MADFIL, PARCOD, PARM, INDEX)
  INTEGER MADFIL

  Sets 2d parameter array

  MADFIL - File handle
  PARCOD - Parameter code
  PARM    - Parameter value
  INDEX   - Position of parameter in 2d array (1<=INDEX<=MPAR)
  
    Note: to set special value missing, use PARM=1.e-38.
      To set special value assumed (for error parms only), use PARM=2.e-38
      To set special value knownbad (for error parms only), use PARM=3.e-38
________________________________________________________

DOUBLE PRECISION FUNCTION MDSSFA(PARCOD)
  INTEGER PARCOD

  Gets parameter scale factor

  PARCOD - Parameter code

  Returns: Parameter scale factor
________________________________________________________________________

SUBROUTINE MDGERR(ERROR)
  CHARACTER ERROR(128)

  Gets most recent error message

  ERROR  - Error message
________________________________________________________________________

DOUBLE PRECISION FUNCTION GETKEY(YEAR,MON,DAY,HOUR,MIN,SEC)
  INTEGER YEAR,MON,DAY,HOUR,MIN,SEC

  Gets key (number of seconds) since YEAR,MON,DAY,HOUR,MIN,SEC
  
  
________________________________________________________________________


SUBROUTINE MDGEOD(MADFIL, ROW, GDLAT, GLON, GDALT)
  INTEGER MADFIL
  DOUBLE PRECISION GDLAT(NRANMX)
  DOUBLE PRECISION GLON(NRANMX)
  DOUBLE PRECISION GDALT(NRANMX)  

  Gets GDLAT, GLON, GDALT from current record via cedarGetGeodetic.

  MADFIL - File handle, pointing to current record
  GDLAT - geodetic latitude array
  GLON - longitude array
  GDALT - geodetic altitude array
________________________________________________________________________

SUBROUTINE GTROOT(STROOT,LENGTH)
  CHARACTER STROOT(128)
  INTEGER LENGTH

  Gets MADROOT as set either in env variable or in cedar.h

  STROOT  - String holding MADROOT
  LENGTH - length of string copied
________________________________________________________________________


*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <sys/types.h>
#include <sys/ipc.h>
#include <sys/file.h>
#include <cedarIO.h>
#include <madrec.h>
#include <cedar.h>
#include <date.h>

#define NRANMX 500
#define MXMADFILS 10

/* prototypes */
int copyF77String(char * str, int len, char * buf, int bufsize);

Madrec *madrecsp[MXMADFILS];

int diag=0;

int mdopen_(int *iotype, char *filec, int length)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    int i =0; 
    int status = -1;
    int ret_val = 0;
    Madrec *madrecp;
    static char *err2="madrecOpen error";
    char err[256];
    char * c_filec = NULL; /* c version of fortran string */

    if (diag) {
        printf("Entering cedaropen\n");
    }

    status = cedarReadParCodes();
    if (status != 0) {
        return(status);
    }

    madrecp = madrecCreate();
    
    /* find open slot, if any */
    for (i=0; i < MXMADFILS; i++)
    {
        if (madrecsp[i] == NULL)
        {
            madrecsp[i] = madrecp;
            status = 0;
            ret_val = i;
            break;
        }
    }
    
    /* if no open slot, return error */
    if (status == -1)
        return (status);


    /* create c version of string */
    c_filec = malloc(length + 2);
    copyF77String(filec, length, c_filec, length + 2);

    status = madrecOpen(madrecp, *iotype, c_filec);
    if (status != 0) 
    {
        sprintf(err, "%s - Cannot open %s\n", err2, c_filec);
        cedarSetError(err);
	free(c_filec);
        return(-2);
    }
    
    free(c_filec);
    
    if (diag) {
        printf("Exiting cedaropen\n");
	
    }

    return(ret_val);
}


int mdclos_(int *madfile)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    int status;
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
 
    if (diag) {
        printf("Entering cedarclose\n");
    }

   if (madrecp != (Madrec *)NULL) {
        status = madrecClose(madrecp);
        madrecDestroy(madrecp);
        madrecsp[*madfile] = NULL;
    } else {
        return(2);
    }

    if (diag) {
        printf("Exiting cedarclose\n");
    }

    return(status);
}


int mdread_(int *madfile)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    int status;
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    status = madrecGetNextRec(madrecp);
    return(status);
}


int mdwrit_(int *madfile)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    int status;
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    status = madrecPutNextRec(madrecp);
    return(status);
}


int rewind_(int *madfile)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    int status;
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    status = madrecRewind(madrecp);
    return(status);
}


int grecno_(int *madfile, int *recno)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    int status;
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    status = madrecGetRecByRecno(madrecp, (*recno)-1);
    return(status);
}


int grckey_(int *madfile, double *key)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    int status;
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    status = madrecGetRecByKey(madrecp, *key);
    return(status);
}


int mdcopy_(int *madfile1, int *madfile2)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    int status;
    Madrec *madrecp1;
    Madrec *madrecp2;

    madrecp1 = madrecsp[*madfile1];
    madrecp2 = madrecsp[*madfile2];
    status = madrecCopy(madrecp1, madrecp2);
    return(status);
}


int mdisdr_(int *madfile)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    if (madrecp->recordp[1] == CATALOGBIN ||
        madrecp->recordp[1] == HEADERBIN ||
        madrecp->recordp[1] == CATALOGASCII ||
        madrecp->recordp[1] == HEADERASCII) {
        return 0;
    } else {
        return 1;
    }
}


double gtpmin_(int *madfile, int *parcode)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;
    int i = 0;

    madrecp = madrecsp[*madfile];
    
    /* check that iotype right */
    if (madrecp->iotype < 30 || madrecp->iotype > 44)
        return (missing);

    /* loop through all parameters to find a match */
    for (i=0; i<madrecp->numParms; i++)
    {
        if (madrecp->parmsListp[i] == *parcode)
            return madrecp->parmMinp[i];
    }
    
    /* not found */
    return (missing);
}


double gtpmax_(int *madfile, int *parcode)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;
    int i = 0;

    madrecp = madrecsp[*madfile];
    
    /* check that iotype right */
    if (madrecp->iotype < 30 || madrecp->iotype > 44)
        return (missing);

    /* loop through all parameters to find a match */
    for (i=0; i<madrecp->numParms; i++)
    {
        if (madrecp->parmsListp[i] == *parcode)
            return madrecp->parmMaxp[i];
    }
    
    /* not found */
    return (missing);
}


void mdcrea_(int *madfile,
            int *lprol, int *jpar, int *mpar, int *nrow,
            int *krec, int *kinst, int *kindat,
            int *year1, int *month1, int *day1,
            int *hour1, int *minute1, int *second1, int *centisecond1,
            int *year2, int *month2, int *day2,
            int *hour2, int *minute2, int *second2, int *centisecond2)    
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];

    if (diag) {
        printf("Entering cedarcreate\n");
    }

    madrecp->recordp =
        cedarCreateRecord(*lprol, *jpar, *mpar, *nrow,
                          *krec, *kinst, *kindat,
                          *year1, *month1, *day1,
                          *hour1, *minute1, *second1, *centisecond1,
                          *year2, *month2, *day2,
                          *hour2, *minute2, *second2, *centisecond2);

    if (diag) {
        printf("Exiting cedarcreate\n");
    }
}


void mdg1dp_(int *madfile, int *parcode, double *parm)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    *parm = cedarGet1dParm(madrecp->recordp, *parcode);
}

int mdgnrw_(int *madfile) 
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    return(cedarGetNrow(madrecp->recordp));
}


int mdgkst_(int *madfile) 
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    return(cedarGetKinst(madrecp->recordp));
}


int mdgkdt_(int *madfile) 
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    return(cedarGetKindat(madrecp->recordp));
}


int mdibyr_(int *madfile) 
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    return(cedarGetIbyr(madrecp->recordp));
}


int mdibdt_(int *madfile) 
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    return(cedarGetIbdt(madrecp->recordp));
}


int mdibhm_(int *madfile) 
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    return(cedarGetIbhm(madrecp->recordp));
}


int mdibcs_(int *madfile) 
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    return(cedarGetIbcs(madrecp->recordp));
}


int mdieyr_(int *madfile) 
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    return(cedarGetIeyr(madrecp->recordp));
}


int mdiedt_(int *madfile) 
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    return(cedarGetIedt(madrecp->recordp));
}


int mdiehm_(int *madfile) 
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    return(cedarGetIehm(madrecp->recordp));
}


int mdiecs_(int *madfile) 
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    return(cedarGetIecs(madrecp->recordp));
}


void mdg2dp_(int *madfile, int *parcode, double *parm)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    int i,nrow;
    double *p;
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];

    nrow = cedarGetNrow(madrecp->recordp);
    if (nrow > NRANMX) nrow=NRANMX;
    p = cedarGet2dParm(madrecp->recordp, *parcode);
    for (i=0; i<nrow; i++) {
        parm[i] = p[i];
    }
    free(p);
}


void mdgflt_(int *madfile, int *parcode, double *parm)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    int i,nrow;
    double *p;
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];

    nrow = cedarGetNrow(madrecp->recordp);
    if (nrow > NRANMX) nrow=NRANMX;
    p = cedarGetFlatParm(madrecp->recordp, *parcode);
    for (i=0; i<nrow; i++) {
        parm[i] = p[i];
    }
    free(p);
}


void mds1dp_(int *madfile, int *parcode, double *parm, int *index)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    madrecp = madrecsp[*madfile];
    cedarSet1dParm(madrecp->recordp, *parcode, *parm, *index-1);
}


void mds2dp_(int *madfile, int *parcode, double *parm, int *index)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    Madrec *madrecp;

    /* Indices start a 0 in C, 1 in Fortran */
    madrecp = madrecsp[*madfile];
    
    cedarSet2dParm(madrecp->recordp, *parcode, parm, *index-1);
}


double mdgsfa_ (int *parcode)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    double scalefactor;

    scalefactor = cedarGetParScaleFactor (*parcode);
    return(scalefactor);
}


void mdgerr_ (char *error, short length)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    char *err;
    int len = 0;

    err = cedarGetError();
    len = strlen(error);
    if (len > length) len=length;
    strncpy(error, err, len);
}

double getkey_(int *year, int *month, int *day, int *hour, int *min, int *sec)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    return (getKey(*year, *month, *day, *hour, *min, *sec));
}


void mdgeod_(int *madfile, double *gdlat, double *glon, double *gdalt)
{

    /* meant to be called from Fortran - see Fortran comments above for documentation */
    int i,nrow;
    Madrec *madrecp;
    double *gdlatpp = NULL;
    double *glonpp = NULL;
    double *gdaltpp = NULL;

    madrecp = madrecsp[*madfile];

    nrow = cedarGetNrow(madrecp->recordp);
    if (nrow > NRANMX) nrow=NRANMX;
    cedarGetGeodetic(madrecp->recordp, &gdlatpp, &glonpp, &gdaltpp);
    
    for (i=0; i<nrow; i++) 
    {
        gdlat[i] = gdlatpp[i];
        glon[i] = glonpp[i];
        gdalt[i] = gdaltpp[i];
    }
    
    /* free memory */
    if (gdlatpp != NULL)
    {
        free(gdlatpp);
        free(glonpp);
        free(gdaltpp);
    }
    
}


void gtroot_ (char *madrootstr, int *lenrot, short length)
{
    /* meant to be called from Fortran - see Fortran comments above for documentation */
    char tmp[2000];

    cedarGetMadroot(tmp);
    *lenrot = strlen(tmp);
    if (*lenrot > length) *lenrot=length;
    strncpy(madrootstr, tmp, *lenrot);
}

