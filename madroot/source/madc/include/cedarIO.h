/*  $Id: cedarIO.h 3304 2011-01-17 15:25:59Z brideout $ */

#ifndef _CEDARIOH_
#define _CEDARIOH_

enum {
        CATALOGBIN = 2001,     /* Binary catalog record code (krec) */
        HEADERBIN = 3002,      /* Binary header record code (krec) */
        DATABIN = 1002,        /* Binary data record code (krec) */
        CATALOGASCII = 2101,   /* Ascii catalog record code (krec) */
        HEADERASCII = 3101,    /* Ascii header record code (krec) */
        DATAASCII = 1101       /* Ascii data record code (krec) */
};

typedef short Int16;

int getNextMadrigalRecord(FILE *, Int16 **, int,
			  int *);
int putNextMadrigalRecord (FILE *, Int16 **, int,
			   int *, Int16 **, int *, int *);

int getNextCedarAsciiRecord(FILE *, Int16 **);
int putNextCedarAsciiRecord(FILE *, Int16 **);

int getNextCedarCbfRecord(FILE *, Int16 **, int, int, int *, int *,
		          int *, int *, int *, int *, int *, Int16 **);
int putNextCedarCbfRecord(FILE *, Int16 **, int,
		         int *, int *, Int16 **, int*, int*, int*, long *);
int flushCedarCbfRecord(FILE *, Int16 **, int,
		        int *, int *, Int16 **, int*, int*, int*, long *);
int endFileCedarCbfRecord(FILE *, Int16 **, int, int*, long *);
int endDataCedarCbfRecord(FILE *, Int16 **, int, long *);
int getNextCosRecord(FILE *, Int16 **, int *);
int putNextCosRecord(FILE *, Int16 **,
                     int, int*, int*, int*, int*, long*);
int writeCbfControlWord(FILE *,
                        int, int, int, int, int, int, long *);

int getNextCedarBlockedRecord(FILE *, Int16 **, Int16 *, int *);
int putNextCedarBlockedRecord(FILE *, Int16 **, int*, int *, int *, Int16 **);
int flushCedarBlockedRecord(FILE *, Int16 **, int*, int *, int *, Int16 **);

int getNextCedarUnblockedRecord(FILE *, Int16 **);
int putNextCedarUnblockedRecord(FILE *, Int16 **);

int getMemNextCedarUnblockedRecord(Int16 **, Int16 **, int *, int *);
int putMemNextCedarUnblockedRecord(Int16 **, Int16 **, int *, int *);
int putMemFastNextCedarUnblockedRecord(Int16 **, Int16 **, int *, int *, int *);
int editMemNextCedarUnblockedRecord(Int16 **, Int16 **, int *, int *);

int cedarFileType(char *, int, int);
int isProlog(Int16*);

int setCheckSum(int, Int16 **);
unsigned int decodeBits(unsigned char *, unsigned int, unsigned int);
void encodeBits(unsigned char *, unsigned int, unsigned int, unsigned int);
int jday(int, int, int);
int jday1(int, int, int);
int idmyk1(int, int, int);
void dumpCedarRecord(Int16 **, char*);

size_t fread16(void *ptr, size_t size, size_t nitems, FILE *stream);

size_t fwrite16(void *ptr, size_t size, size_t nitems, FILE *stream);

void reorderBytes(Int16 * ptr, int numInt16s);

#endif
