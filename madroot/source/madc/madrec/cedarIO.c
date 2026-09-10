/*  $Id: cedarIO.c 3699 2011-10-19 17:55:43Z brideout $ */

/*
modification history
--------------------
00a, 16 March, 2000         original
*/

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <ctype.h>
#include <cedarIO.h>

int DEBUG=0;

/***********************************************************************
*
* getNextMadrigalRecord  reads a madrigal record
*
* The file should be positioned at the beginning of a record before
* calling this function, and on the first call, the Cedar record
* pointer, *cedarRecord, should be NULL. The pointers at the beginning
* of each block (words 1 and 2) and the checksum (word(blockSize-1) are
* ignored.
*
* Madrec completely ignores the 5 extra control words, words 17-21, in the
* Madrigal format prolog. They are removed when a Madrigal record is read 
* and added when a Madrigal record is written.
* These extra words are fully compliant with the CEDAR binary format in
* the case of data records, since the prolog length is specified in the
* data record.  They are not fully compliant with the CEDAR standard in
* the case of binary catalog and header records, which have fixed prolog
* lengths of 40, of which only the first 12 and 15 respectively are
* significant. The standard requires that the remaining words in the
* prolog must be zero. However, in practice this has often been ignored,
* even at NCAR, and it is unlikely that any CEDAR software actually
* chokes at non-zero words beyond 12 and 15 in catalog and header
* records.
*
*    fp          - File pointer to the Madrigal file
*    cedarRecord - The Cedar record
*    blockSize   - Madrigal file block size. Normally 6720 16-bit integers.
*    sigWords    - Number of signifcant words in the current block
*
*/

int
getNextMadrigalRecord (FILE *fp, Int16 **cedarRecordpp,
                       int blockSize,
                       int *sigWordsp)
{
    int i=0, j=0, numBlocks=0, ltot=0, krec=0, lprol=0;
    long pos=0, posInit=0, fileSize=0;
    Int16 blockHeader[3], checkSum=0, word=0;

    /* Initialization */
    pos = ftell(fp)/2;
    posInit = pos;
    (void) fseek(fp, 0L, SEEK_END);
    fileSize = ftell(fp)/2;
    (void) fseek(fp, 2*(blockSize*(pos/blockSize)), SEEK_SET);
    if (fread16(&blockHeader, (size_t) 2, (size_t) 3, fp) != 3) {
        (void) fseek(fp, 2*pos, SEEK_SET);
        return(-11);
    }
    *sigWordsp = blockHeader[0];
    (void) fseek(fp, 2*pos, SEEK_SET);
    numBlocks = fileSize/blockSize;
    if (blockSize*numBlocks != fileSize) {
        (void) printf("%s\n", strerror(ferror(fp)));
        return(-2);
    }
    if (*cedarRecordpp != (Int16 *)NULL) {
        free(*cedarRecordpp);
        *cedarRecordpp = (Int16 *)NULL;
    }

    for (;;) {

        /* Handle control words at beginning of block */
        if (pos == blockSize*(pos/blockSize)) {
            if (fread16(&blockHeader, (size_t) 2, (size_t) 3, fp) != 3) {
                return(-3);
            }
            *sigWordsp = blockHeader[0];
            pos = pos + 3;

        /* Handle checksum */
        } else if (pos+1 == *sigWordsp + (pos/blockSize)*blockSize) {
            if (fread16(&checkSum, (size_t) 2, (size_t) 1, fp) != 1) {
                return(-4);
            }
            pos++;

        /* Return if end-of-file */
        } else if (pos > (numBlocks-1)*blockSize+*sigWordsp) {
            if (*cedarRecordpp != (Int16 *)NULL) {
                free(*cedarRecordpp);
                *cedarRecordpp = (Int16 *)NULL;
            }
            (void) fseek(fp, 2*posInit, SEEK_SET);
            return(-1);

        /* Read next word of current record */
        } else {
            if (fread16(&word, (size_t) 2, (size_t) 1, fp) != 1) {
                (void) fprintf(stderr, "ftell = %ld\n", ftell(fp)/2);
                (void) fprintf(stderr,"pos,*sigWordsp = %ld %d\n", 
                    pos,*sigWordsp);
                return(-5);
            }

            if (i == 0) {
                ltot = word;
                /* Return if end-of-file */
                if (ltot == 0) {            /* EOF */
                    if (*cedarRecordpp != (Int16 *)NULL) {
                        free(*cedarRecordpp);
                        *cedarRecordpp = (Int16 *)NULL;
                    }
                    (void) fseek(fp, 2*posInit, SEEK_SET);
                    return(-1);
                } else if (ltot >= 21) {    /* So far so good */
                    *cedarRecordpp = (Int16 *)malloc(ltot*sizeof(Int16));
                } else {
                    return(-6);                /* Impossibly short record */
                }
                (*cedarRecordpp)[j] = ltot;


            } else if (i == 1) {
                krec = word;
                if (krec != CATALOGBIN && krec != HEADERBIN) {
                    (*cedarRecordpp)[j] = ltot - 5;
                }
                j++;    /* j is position in madrec record */
                (*cedarRecordpp)[1] = krec;

            } else if (i == 12) {
                lprol = word;
                if (lprol != 21) {
                    if (*cedarRecordpp != (Int16 *)NULL) {
                        free(*cedarRecordpp);
                        *cedarRecordpp = (Int16 *)NULL;
                    }
                    return(-9);
                }
                j++;
                /* set lprol to what it should be - now
                   is always 21 in Madrigal files for compatibility with old fortran
                   routines, but we convert to correct values when read into memory */
                if (krec != CATALOGBIN)
                	(*cedarRecordpp)[j] = 16;
                else
                    (*cedarRecordpp)[j] = 0;

            } else if (i >= 16 && i <= 20) { 
                if (krec == CATALOGBIN || krec == HEADERBIN) {
                    j++;
                    (*cedarRecordpp)[j] = 0;
                }

            } else {
                j++;
                (*cedarRecordpp)[j] = word;
                /* Return on end of record */
                if (i == ltot-1) {
                    /* If this is a header or catalog record, need to
                       put bytes back in right order that fread16 may have switched */
                    if ((*cedarRecordpp)[1] == CATALOGBIN || (*cedarRecordpp)[1] == HEADERBIN) {
                        reorderBytes((*cedarRecordpp) + 40, (*cedarRecordpp)[0] - 40);
                    }
                    return(0);
                }
             }

            i++;        /* position in input file record */
            pos++;      /* position in madrigal file */
        }
    }
}


/***********************************************************************
*
* putNextMadrigalRecord   adds madrigal record to a Madrigal file
*
* Madrigal files written by the Fortran library have an extra 0 after
* the last record. This may serve as an EOF indicator (zero-length record).
* This is not in the specification and is not added by this routine. 
* getNextMadrigalRecord handles the extra zero correctly.
*
* Cedar data records may have a shorter or longer prolog than data records
* in a Madrigal file, which always have a 21-word prolog. So, this routine
* transfers data from the input Cedar record to a Madrigal record,
* modifying the prolog as required, and then outputs the Madrigal
* record.
*
*    fp          - File pointer to the Madrigal file
*    cedarRecord - The Cedar record
*    blockSize   - 
*    blockIndex  - Madrigal file block size. Normally 6720 16-bit integers.
*    block       - The Madrigal block - normally 2*6720=13440 bytes.
*    prevRec     - Position of previous record in its block
*    thisRec     - Position of current record in its block.
*  
*/

int
putNextMadrigalRecord (FILE *fp, Int16 **cedarRecordpp,
                       int blockSize,
                       int *blockIndexp,
                       Int16 **blockpp,
                       int *prevRecp,
                       int *thisRecp)
{
    int i=0, sigWords=0, ltot=0, krec=0, lprol=0, lpthis=0, pastProlog=0;
    long pos=0;
    int madptr(Int16 *);
    Int16 *madRecordp;

    if (DEBUG) dumpCedarRecord(cedarRecordpp, "putNextMadrigalRecord - cedarRecordpp");

    ltot = (*cedarRecordpp)[0];
    krec  = (*cedarRecordpp)[1];
    lprol = (*cedarRecordpp)[12];

    /* Zero out extra words in catalog and header record prologs */
    if (krec == CATALOGBIN) {
        for(i=12; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    } else if (krec == HEADERBIN) {
        for(i=15; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    }

    /* Allocate space for block if necessary */
    if (*blockpp == (Int16 *)NULL) {
        *blockpp = (Int16 *)malloc(blockSize*sizeof(Int16));
        for (i=0; i<blockSize; i++)
            (*blockpp)[i] = 0;
    }

    /* 
    Allocate memory for the Madrigal record prolog.
    Catalog and header records are special beasts with 40 word
    prologs. In these records, lprol refers to the associated
    data records, rather than the current record. We assume that
    in all other cases, including data records and records whose
    type is unknown, lprol refers to the current record. In
    practice, the actual length of the prolog does not matter for
    such records, as long as it is not greater than 16. If the
    prolog length is greater than 16, words 17-21 will be
    overwritten by the 5 special prolog words in the Madrigal
    format.
    */

    /* Construct the prolog (40 words for catalog and header records,
       21 words for all other record types */

    if (krec == CATALOGBIN || krec == HEADERBIN) {
        lpthis = 40;
        pastProlog = 40;
    } else {
        ltot = ltot - lprol + 21;
        lpthis = 21;
        pastProlog = lprol;
    }
    madRecordp = (Int16 *)malloc(lpthis*sizeof(Int16));

    /* Copy the prolog of the Cedar record to the Madrigal record */
    (void) memcpy(madRecordp, *cedarRecordpp, lpthis*sizeof(Int16));

    /* Set prolog length and previous record pointer */
    madRecordp[0] = ltot;
    madRecordp[12] =  21;
    madRecordp[16] =  *prevRecp;

    /* Insert 32-bit start and end times in prolog */
    madRecordp[17] =  madptr(&(*cedarRecordpp)[4]) >> 16;
    madRecordp[18] = (madptr(&(*cedarRecordpp)[4]) << 16) >> 16;
    madRecordp[19] =  madptr(&(*cedarRecordpp)[8]) >> 16;
    madRecordp[20] = (madptr(&(*cedarRecordpp)[8]) << 16) >> 16;

    /* Copy remainder of Cedar record to Madrigal record */
    madRecordp = (Int16 *)realloc(madRecordp, madRecordp[0]*sizeof(Int16));
    (void) memcpy(madRecordp+lpthis,
                  *cedarRecordpp+pastProlog,
                  (madRecordp[0]-lpthis)*sizeof(Int16));

    /* if this is a header or catalog record, need to reorder bytes
       so that fwrite16 does not misorder them.  Note that there
       is no need to put these bytes back in the right order at the
       end of this function because madRecordp is temporary
       memory that is deallocated at the end. */
    if (krec == CATALOGBIN || krec == HEADERBIN) {
        reorderBytes(madRecordp+lpthis, madRecordp[0]-lpthis);
    }

    if (*blockIndexp == 0) {
        /* record starts at the beginning of a block */
        (*blockpp)[1] = 3;
        (*blockpp)[2] = 3;
        *blockIndexp = 3;
    } else {
        if ((*blockpp)[1] == 0)
            (*blockpp)[1] = *blockIndexp;
        (*blockpp)[2] = *blockIndexp;
    }

    *prevRecp = *thisRecp;
    *thisRecp = *blockIndexp;

    for (i=0; i<madRecordp[0]; i++) {
        (*blockpp)[*blockIndexp] = madRecordp[i];
        if (i == 16) (*blockpp)[*blockIndexp] = *prevRecp;
        if (*blockIndexp == blockSize-2) {
            /* At end of block. So write it and go to next block */
            (*blockpp)[0] = blockSize;
            (void) setCheckSum (blockSize, blockpp);
            (void) fwrite16(*blockpp, (size_t) 2, (size_t) blockSize, fp);
            (*blockpp)[1] = 0;
            (*blockpp)[2] = 0;
            *blockIndexp = 3;
        } else {
            (*blockIndexp)++;
        }
    }

    /* The entire record has been written. So, write to file and return */
    pos = ftell(fp);
    sigWords = *blockIndexp + 1;
    if (sigWords < blockSize)
        sigWords++;
    (*blockpp)[0] = sigWords;
    for (i=*blockIndexp; i<blockSize-1; i++) {
        (*blockpp)[i] = 0;
    }
    (void) setCheckSum (sigWords, blockpp);

    pos = ftell(fp);
    (void) fwrite16(*blockpp, (size_t) 2, (size_t) blockSize, fp);
    (void) fflush(fp);
    (void) fseek(fp, pos, SEEK_SET);

    free(madRecordp);

    if (DEBUG) dumpCedarRecord(&madRecordp, "putNextMadrigalRecord - madRecordp");

    return(0);
}


/***********************************************************************
*
* getNextCedarAsciiRecord   reads record in CEDAR ASCII format
*
*    fp          - File pointer to the Madrigal file
*    cedarRecord - The Cedar record
*
*/

int
getNextCedarAsciiRecord (FILE *fp, Int16 **cedarRecordpp)
{
    int nlines=0, ltot=0, krec=0, jpar=0, mpar=0, nrow=0, lprol=0,
        i=0, j=0, word=0;
    char *s, ss[200];

    /* Allocate space for the first 16 words of the prolog */
    if (*cedarRecordpp != (Int16 *)NULL) {
        free(*cedarRecordpp);
	*cedarRecordpp = (Int16 *)NULL;
    }
    *cedarRecordpp = (Int16 *)malloc(16*sizeof(Int16));

    /* Read the first 16 words of the prolog */
    for (i=0; i<16; i++) {
        if (fscanf(fp, "%hd", &(*cedarRecordpp)[i]) != 1) {
            free(*cedarRecordpp);
            *cedarRecordpp = (Int16 *)NULL;  
            return(-1);
        }
    }
    nlines  = (*cedarRecordpp)[0];    /* Number of lines in the record */
    krec  = (*cedarRecordpp)[1];      /* Type of record */

    /* Calculate the total length of the record
       This is not the same as ltot in the Ascii file */
    if (krec == 1101) {

        lprol = (*cedarRecordpp)[12];
        jpar = (*cedarRecordpp)[13];
        mpar = (*cedarRecordpp)[14];
        nrow = (*cedarRecordpp)[15];
        ltot = lprol + 2*jpar + mpar*(nrow+1);

        /* Allocate additional space for the full record */
        *cedarRecordpp = (Int16 *)realloc(*cedarRecordpp, ltot*sizeof(Int16));

        /* Set words 0, 1 and 12 of the prolog, which have different values
           than in the ASCII record */
        (*cedarRecordpp)[0] = ltot;
        (*cedarRecordpp)[12] = lprol;
        (*cedarRecordpp)[1] = 1002;
        for (i=lprol; i<ltot; i++) {
           /*  if (fscanf(fp, "%d", &(*cedarRecordpp)[i]) != 1) { */
            if (fscanf(fp, "%6d", &word) != 1) {
                free(*cedarRecordpp);
                *cedarRecordpp = (Int16 *)NULL;  
                return(-3);
            }
            if (word > 32767 || word < -32768) {
	        fprintf(stderr, "Illegal 16 bit integer %i found at start time - year: %i, mmdd: %i, hhmm: %i\n",
		        word, (*cedarRecordpp)[4], (*cedarRecordpp)[5], (*cedarRecordpp)[6]);
                return(-4);
            }
            (*cedarRecordpp)[i] = word;
        }

    } else if (krec == 2101 || krec == 3101) {

        /* Allocate additional space for the full record */
        /* Note that we are reading only the first 80 bytes of header or catalog*/
        /* If longer, we are truncating */
        ltot = 40*nlines;
        (*cedarRecordpp)[0] = ltot;
        *cedarRecordpp = (Int16 *)realloc(*cedarRecordpp, ltot*sizeof(Int16));

        /* Fill remainder of first card image (prolog) with zeroes */
        for (i=15; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }

        /* Change krec to appropriate binary value */
        if ((*cedarRecordpp)[1] == 2101) {          /* Catalog record */
            (*cedarRecordpp)[1] = 2001;
        } else if ((*cedarRecordpp)[1] == 3101) {   /* Header record */
            (*cedarRecordpp)[1] = 3002;
        }

        /* Get remainder of catalog or header record */
        (void) fgets(ss, 200, fp); /* Finish off first line */
        for (i=1; i<nlines; i++) {
            s = (char *) (*cedarRecordpp + 40*i);
            for (j=0; j<80; j++) {
                s[j] = ' ';
            }
 
           (void) fgets(ss, 200, fp);

            if (strlen(ss) >= 2) {
                /* if j > 80, just skip */
                for (j=0; j<=strlen(ss)-2; j++) {
                    if (j >= 80)
                        continue;
                    s[j] = ss[j];
                }
            }
        }

    } else {
        fprintf(stderr, "Illegal krec for ascii cedar file: %i\n", krec);
        free(*cedarRecordpp);
        *cedarRecordpp = (Int16 *)NULL;  
        return(-2);
    }

    if (DEBUG) dumpCedarRecord(cedarRecordpp, "getNextCedarAsciiRecord");

    return(0);
}


/***********************************************************************
*
* putNextCedarAsciiRecord   writes record in CEDAR ASCII format
*
*    fp          - File pointer to the Madrigal file
*    cedarRecord - The Cedar record
*
*/

int
putNextCedarAsciiRecord (FILE *fp, Int16 **cedarRecordpp)
{
    int ltot=0, jpar=0, mpar=0, nrow=0, nlines=0, krec=0, i=0, j=0, k=0;
    int nint=20, lprol=16;
    char *s;

    if (DEBUG) dumpCedarRecord(cedarRecordpp, "putNextCedarAsciiRecord - cedarRecordpp");

    ltot = (*cedarRecordpp)[0];
    krec = (*cedarRecordpp)[1];

    if (krec == 1002 || krec == 1101) {   /* Data record */
        krec = 1101;
        jpar = (*cedarRecordpp)[13];
        mpar = (*cedarRecordpp)[14];
        nrow = (*cedarRecordpp)[15];

    nlines = 1 + 2*((jpar+19)/nint) + (nrow+1)*((mpar+19)/nint);
    
    /* Write Prolog */
    k = -1;
    for (i=1; i<=lprol; i++) {
        k++;
        if (i == 1) {
            (void) fprintf(fp, "%6d", nlines);
        } else if (i == 2) {
            (void) fprintf(fp, "%6d", krec);
        } else if (i == 13) {
            (void) fprintf(fp, "%6d", lprol);
        } else {
            (void) fprintf(fp, "%6d", (*cedarRecordpp)[k]);
        }
        if (i == nint*(i/nint) || i == lprol) {
            (void) fprintf(fp, "\n");
        }
    }

    /* Write 1-d array */
    k = (*cedarRecordpp)[12]-1;   /* Skip any prolog words after 16th */
    for (j=0; j<2; j++) {
        for (i=1; i<=jpar; i++) {
            k++;
            (void) fprintf(fp, "%6d", (*cedarRecordpp)[k]);
            if (i == nint*(i/nint) || i == jpar) {
                (void) fprintf(fp, "\n");
            }
        }
    }

    /* Write 2-d array */
    for (j=0; j<=nrow; j++) {
        for (i=1; i<=mpar; i++) {
            k++;
            (void) fprintf(fp, "%6d", (*cedarRecordpp)[k]);
            if (i == nint*(i/nint) || i == mpar) {
                 (void) fprintf(fp, "\n");
            }
        }
    }

    } else if (krec == CATALOGBIN || krec == HEADERBIN) {

        /* Zero out extra words in catalog and header record prologs */
        if (krec == CATALOGBIN) {             /* Catalog record */
            nlines = ltot/40;
            (*cedarRecordpp)[0] = nlines;
            (*cedarRecordpp)[1] = 2101;
            for(i=12; i<40; i++) {
                (*cedarRecordpp)[i] = 0;
            }
        } else if (krec == HEADERBIN) {       /* Header record */
            nlines = ltot/40;
            (*cedarRecordpp)[0] = nlines;
            (*cedarRecordpp)[1] = 3101;
            for(i=15; i<40; i++) {
                (*cedarRecordpp)[i] = 0;
            }
        }

        /* Write prolog */
        for (j=0; j<20; j++) {
            (void) fprintf(fp, "%6d", (*cedarRecordpp)[j]);
        }
        (void) fputc('\n', fp);

        /* Write remainder of record */
        for (i=1; i<nlines; i++) {
            s = (char *) (&((*cedarRecordpp)[40*i]));
            for (k=79; k>=0; k--) {
                if (isgraph((int)s[k])) break;
            }
            for (j=0; j<=k; j++) {
                (void) fputc(s[j], fp);
            }   
            (void) fputc('\n', fp);            
        }     
    }

    return(0);
}


/***********************************************************************
*
* getNextCedarCbfRecord   Gets the next CEDAR record from a CBF file
*
*    fp          - File pointer to the Madrigal file
*    cedarRecord - The Cedar record
*    blockSize   -
*    lCosBlock   -
*    pos         - position within Cos record, which contains multiple
*                    Cedar records
*    fwi         -
*    cosRecord   -
*
*/
int
getNextCedarCbfRecord(FILE *fp, Int16 **cedarRecordpp,
                      int forceCosRead,
                      int blockSize,
                      int *initPos8p,
                      int *initFwip,
                      int *initPosp,
                      int *initLCosBlockp,
                      int *lCosBlockp,
                      int *posp,
                      int *fwip,
                      Int16 **cosRecordpp)
{
    int i=0, ltot=0, ind=0;

    /* Read the next Cos record */
    if (forceCosRead) {    /* Always read Cos record if random read */
        (void) fseek(fp, *initPos8p, SEEK_SET);
        *fwip = *initFwip;
        ind = getNextCosRecord(fp, cosRecordpp, fwip);
        *posp = *initPosp;
        *lCosBlockp = *initLCosBlockp;
    } else if (*posp >= *lCosBlockp-1) {
        *initPos8p = ftell(fp);
        *initFwip = *fwip;
        ind = getNextCosRecord(fp, cosRecordpp, fwip);
        if (ind == 8) {    /* This is first Cedar record in the Cos record */
            *posp = 1;
            *lCosBlockp = (*cosRecordpp)[0];
        } else {
            *posp = 0;
            *lCosBlockp = 0;
        }
    }
    *initPosp = *posp;
    *initLCosBlockp = *lCosBlockp;

    /*
    printf("ind,*pos8p,*fwip,*posp,*lCosBlockp, = %d %d %d %d %d\n", 
    ind,ftell(fp),*fwip,*posp,*lCosBlockp);
    */

    /* Copy first 16 words of prolog into Cedar record, set next 5 words
       to zero, and copy 1-d and 2-d data into record. If the prolog
       has more than 16 words, these are lost. */
    if (*cedarRecordpp != (Int16 *) NULL) {
        free(*cedarRecordpp);
        *cedarRecordpp = (Int16 *) NULL;
    }
    ltot = (*cosRecordpp)[*posp];
    *cedarRecordpp = (Int16 *)malloc(ltot*sizeof(Int16));
    for (i=0; i<ltot;i++) {
      (*cedarRecordpp)[i] = (*cosRecordpp)[*posp+i];
    }

    /* if this is a header or catalog record, need to reorder bytes
       so that fread16 did not misorder them */
    if ((*cedarRecordpp)[1] == CATALOGBIN || (*cedarRecordpp)[1] == HEADERBIN) {
        reorderBytes((*cedarRecordpp) + 40, (*cedarRecordpp)[0] - 40);
    }



    /*
    printf("%d %d %d %d %d %d %d\n", (*cedarRecordpp)[0], (*cedarRecordpp)[1], (*cedarRecordpp)[2],(*cedarRecordpp)[3], (*cedarRecordpp)[4], (*cedarRecordpp)[5], (*cedarRecordpp)[6]);
    */
    if (*cosRecordpp != (Int16 *) NULL) {
        *posp = *posp + (*cosRecordpp)[*posp];
    } else {
        *posp = 0;
    }

    if (ind == 8) {            /* EOR */
        ind = 0;
    } else if (ind == 14) {    /* EOF */
        ind = -1;
    } else if (ind == 15) {    /* EOD */
        ind = -2;
    } else {
        ind = 0;
    }

    return(ind);
}


/***********************************************************************
*
* getNextCosRecord   Gets the next CEDAR record from a CBF file
*
*    fp          - File pointer to the Madrigal file
*    cedarRecord - The Cedar record
*    fwi         -
*
*/
int
getNextCosRecord(FILE *fp, Int16 **cosRecordpp, int *fwip)
{
    int offset=0, n16=0, lbuf=0, m=0;
    unsigned char ctrlwrd[8];
    long pos=0, pos8=0;

    pos8 = ftell(fp);
    pos = 0;
    lbuf = 0;
    offset = 0;

    if (pos8 == 0) {    /* Read and parse first control word in file */
        *cosRecordpp = (Int16 *) NULL;
        (void) fread(ctrlwrd, (size_t) 1, (size_t) 8, fp);
        m = decodeBits(ctrlwrd, 0, 3);
        *fwip = decodeBits(ctrlwrd, 55, 63);
        /* 
        ubc = decodeBits(ctrlwrd, 4, 9);
        bdf = decodeBits(ctrlwrd, 11, 11);
        pfi = decodeBits(ctrlwrd, 20, 39);
        bn = decodeBits(ctrlwrd, 31, 54);
        pri = decodeBits(ctrlwrd, 40, 54);
        */
        pos = pos + 8;
    }

    if (*fwip !=0 && *cosRecordpp != (Int16 *) NULL) {
        free(*cosRecordpp);
        *cosRecordpp = (Int16 *) NULL;
    }

    /*  Read until next record control word */
    for(;;) {

        /* Read next data block */    
        n16 = 4*(*fwip);    /* Number of 16-bit integers to next ctrlwrd */
        lbuf = lbuf + n16;
        if (n16 > 0) {
            if (*cosRecordpp == (Int16 *) NULL) {
                *cosRecordpp = (Int16 *)malloc(n16*sizeof(Int16));
            } else {
                *cosRecordpp = (Int16 *)realloc(*cosRecordpp, lbuf*sizeof(Int16));
            }
        }
        (void) fread16(&((*cosRecordpp)[offset]), (size_t) 2, (size_t) n16, fp);
        offset = offset + n16;
        pos = pos + 2*n16;

        /* Read and parse next control word */
        if (fread(ctrlwrd, (size_t) 1, (size_t) 8, fp) < 1) return(0);
        m = decodeBits(ctrlwrd, 0, 3);
        *fwip = decodeBits(ctrlwrd, 55, 63);
        /*
        ubc = decodeBits(ctrlwrd, 4, 9);
        bdf = decodeBits(ctrlwrd, 11, 11);
        pfi = decodeBits(ctrlwrd, 20, 39);
        bn = decodeBits(ctrlwrd, 31, 54);
        pri = decodeBits(ctrlwrd, 40, 54);
        */

        /* Return if end-of-record, end-of-file or end-of-data */
        if (m==8 || m==14 || m==15) {
            /* fpos = ftell(fp)/2; */
            return(m);
        }
    }
}


/***********************************************************************
*
* putNextCedarCbfRecord   Puts the next CEDAR record into a CBF file
*
*    fp                  - File pointer to the Madrigal file
*    cedarRecord         - The Cedar record
*    blockSize           - Cos Blocksize (normally 4096)
*    lbuf                -
*    pos                 -
*    cosRecord           -
*    blockNumber         -
*    previousFileIndex   -
*    previousRecordIndex -
*    lastControlWord     -
*
*/
int
putNextCedarCbfRecord(FILE *fp, Int16 **cedarRecordpp,
                      int blockSize,
                      int *lbufp,
                      int *posp,
                      Int16 **cosRecordpp,
                      int *blockNumberp,
                      int *previousFileIndexp,
                      int *previousRecordIndexp,
                      long *lastControlWordp)
{
    int i=0, ltot=0, krec=0, maxCosBlock=8000;

    ltot = (*cedarRecordpp)[0];
    krec = (*cedarRecordpp)[1];

    /* Write the current Cos block if the current Cedar record would
       extend it beyond its maximum length */

    if (*lbufp + ltot > maxCosBlock) {

        (*cosRecordpp)[0] = *lbufp;                  /* Set length of Cos block */
        (void) setCheckSum (*lbufp, cosRecordpp);    /* Set checksum */
        (void) putNextCosRecord(fp, cosRecordpp,
                                blockSize,
                                lbufp,
                                blockNumberp,
                                previousFileIndexp,
                                previousRecordIndexp,
                                lastControlWordp);
        /* Reinitialize the Cos block */
        free(*cosRecordpp);
        *cosRecordpp = (Int16 *) NULL;
        *lbufp = 2;
        *posp = 1;
    }

    /* Allocate space for the Cedar record in the Cos block */    
    *lbufp = *lbufp + ltot;
    if (*cosRecordpp == (Int16 *) NULL) {
        *cosRecordpp = (Int16 *)malloc(*lbufp*sizeof(Int16));
    } else {
        *cosRecordpp = (Int16 *)realloc(*cosRecordpp, *lbufp*sizeof(Int16));
    }

    /* Zero out extra words in catalog and header record prologs */
    if (krec == CATALOGBIN) {
        for(i=12; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    } else if (krec == HEADERBIN) {
        for(i=15; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    }

    /* if this is a header or catalog record, need to reorder bytes
       so that fread16 did not misorder them */
    if ((*cedarRecordpp)[1] == CATALOGBIN || (*cedarRecordpp)[1] == HEADERBIN) {
        reorderBytes((*cedarRecordpp) + 40, (*cedarRecordpp)[0] - 40);
    }

    /* Copy the current Cedar record to the Cos block */
    for (i=0; i<ltot; i++) {
        (*cosRecordpp)[*posp] = (*cedarRecordpp)[i];
        (*posp)++;
    }

    /* if this is a header or catalog record, we now put the
       bytes back in their original order */
    if ((*cedarRecordpp)[1] == CATALOGBIN || (*cedarRecordpp)[1] == HEADERBIN) {
        reorderBytes((*cedarRecordpp) + 40, (*cedarRecordpp)[0] - 40);
    }

    return(0);
}


/***********************************************************************
*
* putNextCosRecord   Writes the next Cos record to a CBF file
*
*    fp                  - File pointer to the Madrigal file
*    cedarRecord         - The Cedar record
*    blockSize           -
*    lbuf                -
*    blockNumber         -
*    previousFileIndex   -
*    previousRecordIndex - 
*    lastControlWord     -
*
*/
int
putNextCosRecord(FILE *fp, Int16 **cosRecordpp,
                 int blockSize,
                 int *lbufp,
                 int *blockNumberp,
                 int *previousFileIndexp,
                 int *previousRecordIndexp,
                 long *lastControlWordp)
{
    int i=0, left=0;
    int m=0, ubc=0, bdf=0, pfi=0, bn=0, pri=0;
    Int16 sz[3]={0,0,0};
    long pos8=0;    /* Position in file in bytes */

    pos8 = ftell(fp);

    /* If at beginning of Cos block, write control word  */
    if (pos8 == blockSize*(pos8/blockSize)) {
        m = 0;
        bn = *blockNumberp;
        (void) writeCbfControlWord(fp, m, bdf, bn, ubc, pfi, pri,
                                   lastControlWordp);
        (*blockNumberp)++;
        (*previousFileIndexp)++;
        (*previousRecordIndexp)++;
        pos8 = pos8 + 8;
    }

    /* Write Cedar Binary Record */
    for (i=0; i<*lbufp; i++) {
        (void) fwrite16(*cosRecordpp+i, (size_t) 2, (size_t) 1, fp);
        pos8 = pos8 + 2;
        if (pos8 == blockSize*(pos8/blockSize)) {
            m = 0;
            bn = *blockNumberp;
            (void) writeCbfControlWord(fp, m, bdf, bn, ubc, pfi, pri,
                                       lastControlWordp);
            (*blockNumberp)++;
            (*previousFileIndexp)++;
            (*previousRecordIndexp)++;
            pos8 = pos8 + 8;
        }
    }

    /* Write extra 16-bit words up to 64 bit boundry */
    left = 4*((*lbufp+3)/4) - *lbufp;
    (void) fwrite16(sz, (size_t) 2, (size_t) left, fp);

    /* If the Cedar binary record just filled the cos block, we need to write
       a BCW before the RCW */
    pos8 = ftell(fp);
    if (pos8 == blockSize*(pos8/blockSize)) {
        m = 0;
        bn = *blockNumberp;
        (void) writeCbfControlWord(fp, m, bdf, bn, ubc, pfi, pri,
                                   lastControlWordp);
        (*blockNumberp)++;
        (*previousFileIndexp)++;
        (*previousRecordIndexp)++;
    }

    /* Write EOR */
    m = 8;
    ubc = 16*left;
    pfi = *previousFileIndexp;
    pri = *previousRecordIndexp;
    (void) writeCbfControlWord(fp, m, bdf, bn, ubc, pfi, pri,
                               lastControlWordp);     
    *previousRecordIndexp = 0;

    return(0);
}


/***********************************************************************
*
* flushCedarCbfRecord   Flushes the last CEDAR record into a CBF file
*
*    fp                  - File pointer to the Madrigal file
*    cedarRecord         - The Cedar record
*    blockSize           -
*    lbuf                -
*    blockNumber         -
*    previousFileIndex   -
*    previousRecordIndex - 
*    lastControlWord     -
*
*/
int
flushCedarCbfRecord(FILE *fp, Int16 **cedarRecordpp,
                    int blockSize,
                    int *lbufp,
                    int *posp,
                    Int16 **cosRecordpp,
                    int *blockNumberp,
                    int *previousFileIndexp,
                    int *previousRecordIndexp,
                    long *lastControlWordp)
{

    if (*cosRecordpp == (Int16 *)NULL) {
        return(0);
    }
    (*cosRecordpp)[0] = *lbufp;                  /* Set length of Cos block */
    (void) setCheckSum (*lbufp, cosRecordpp);    /* Set checksum */

    (void) putNextCosRecord(fp, cosRecordpp,
                            blockSize,
                            lbufp,
                            blockNumberp,
                            previousFileIndexp,
                            previousRecordIndexp,
                            lastControlWordp);

    free(*cosRecordpp);
    *cosRecordpp = (Int16 *) NULL;
    *lbufp = 2;
    *posp = 1;
   
    return(0);
}


/***********************************************************************
*
* endFileCedarCbfRecord   Writes end-of-file to a CBF file
*
*    fp                  - File pointer to the Madrigal file
*    cedarRecord         - The Cedar record
*    blockSize           -
*    previousFileIndex   -
*    lastControlWord     -
*
*/
int
endFileCedarCbfRecord(FILE *fp, Int16 **cedarRecordpp,
                                int blockSize,
                                int *previousFileIndexp,
                                long *lastControlWordp)
{
    int m=0, ubc=0, bdf=0, pfi=0, bn=0, pri=0;

    m = 14;
    pfi = *previousFileIndexp;
    (void) writeCbfControlWord(fp, m, bdf, bn, ubc, pfi, pri,
                               lastControlWordp);     
    return(0);
}


/***********************************************************************
*
* endDataCedarCbfRecord   Writes end-of-data CBF file
*
*    fp                  - File pointer to the Madrigal file
*    cedarRecord         - The Cedar record
*    blockSize           -
*    lastControlWord     -
*
*/
int
endDataCedarCbfRecord(FILE *fp, Int16 **cedarRecordpp,
                                int blockSize,
                                long *lastControlWordp)
{
    int i=0, m=0, left=0;
    Int16 zero=0;
    long pos=0;
    unsigned char ctrlwrd[8];

    m = 15;
    for (i=0; i<8; i++) ctrlwrd[i]=0;
    encodeBits(ctrlwrd, 0, 3, (unsigned int) m);
    (void) fwrite(ctrlwrd, (size_t) 1, (size_t) 8, fp);

    /* Extend file to an integral multiple of blockSize */
    pos = ftell(fp);
    left = blockSize*(pos/blockSize) + blockSize - pos;
    if(left > 0 && left < blockSize) {
        for (i=0; i<left; i++) {
            (void) fwrite(&zero, (size_t) 1, (size_t) 1, fp);
        }
    }

    return(0);
}


/***********************************************************************
*
* writeCbfControlWord   Gets the next CEDAR record from a CBF file
*
*    fp           - File pointer to the Madrigal file
*    cedarRecord  - The Cedar record
*    m            -
*    bdf          -
*    bn           -
*    fwi          -
*    ubc          -
*    pfi          -
*    pri          -
*/
int
writeCbfControlWord(FILE *fp,
                    int m,
                    int bdf,
                    int bn,
                    int ubc,
                    int pfi,
                    int pri,
                    long *lastControlWordp)
{
    int i=0, fwi=0;
    unsigned char ctrlwrd[8];

/*
unsigned long long *longp;
int fwis;
*/

    /* Add forward word pointer to previous control word */

    fwi = ftell(fp);

/*
fwis = (fwi-*lastControlWordp-8)/8;
printf("fwi,*lastControlWordp = %d %d\n", fwi,*lastControlWordp);
*/

    if (*lastControlWordp >= 0) {
        (void) fseek(fp, *lastControlWordp, SEEK_SET);
        (void) fread(ctrlwrd, (size_t) 1, (size_t) 8, fp);
        encodeBits(ctrlwrd, 55, 63, (fwi-*lastControlWordp-8)/8);
        (void) fseek(fp, *lastControlWordp, SEEK_SET);
        (void) fwrite(ctrlwrd, (size_t) 1, (size_t) 8, fp);

/*
longp = (unsigned long long *) (&ctrlwrd);
printf(" RW %24llo  %d %d %d %d %d %d %d\n", *longp,m,bdf,bn,ubc,pfi,pri,fwis);
*/

        (void) fseek(fp, (long) fwi, SEEK_SET);
        *lastControlWordp = fwi;
    } else {
        *lastControlWordp = 0;
    }

    for (i=0; i<8; i++) ctrlwrd[i]=0;
    encodeBits(ctrlwrd,  0,  3, m);
    encodeBits(ctrlwrd, 11, 11, bdf);
    if (m == 0) {
        encodeBits(ctrlwrd, 31, 54, bn);
    } else if (m == 8 || m == 14 || m == 15) {
        encodeBits(ctrlwrd, 4,   9, ubc);
        encodeBits(ctrlwrd, 20, 39, pfi);
        encodeBits(ctrlwrd, 40, 54, pri);
    } else {
        return(1);
    }
    (void) fwrite(ctrlwrd, (size_t) 1, (size_t) 8, fp);

/*
longp = (unsigned long long *) (&ctrlwrd);
printf(" WC %24llo  %d %d %d %d %d %d %d\n", *longp,m,bdf,bn,ubc,pfi,pri,fwis);
*/

    return(0);
}


/***********************************************************************
*
* getNextCedarBlockedRecord   Gets the next CEDAR record from a file
*
*    fp          - File pointer to the Madrigal file
*    cedarRecord - The Cedar record
*    lBlockp     - pointer to the length of the current block
*    posp        - pointer to the position within the current block
*
*/
int
getNextCedarBlockedRecord(FILE *fp, Int16 **cedarRecordpp,
                          Int16 *lBlockp,
                          int *posp)
{
    Int16 ltot=0, checkSum=0;

    if (*cedarRecordpp != (Int16 *)NULL) {
        free(*cedarRecordpp);
        *cedarRecordpp = (Int16 *)NULL;
    }

    /* Read the first word in the next block if necessary */
    if (*posp <= 0 || *posp == *lBlockp) {
        *posp = 0;
        if (fread16(lBlockp, (size_t) 2, (size_t) 1, fp) != 1) return(-1);
        if (*lBlockp <= 0) return(-1);
        (*posp)++;
    }

    /* Read the next Cedar record */
    if (fread16(&ltot, (size_t) 2, (size_t) 1, fp) != 1) return(-1);
    *cedarRecordpp = (Int16 *)malloc(ltot*sizeof(Int16));
    *cedarRecordpp[0] = ltot;
    if (fread16(*cedarRecordpp+1, (size_t) 2, (size_t) (ltot-1), fp) != ltot-1) 
        return(-1);

    *posp = *posp + ltot;

    /* if this is a header or catalog record, need to reorder bytes
       so that fread16 did not misorder them */
    if ((*cedarRecordpp)[1] == CATALOGBIN || (*cedarRecordpp)[1] == HEADERBIN) {
        reorderBytes((*cedarRecordpp) + 40, ltot - 40);
    }

    /* Read the checksum if necessary */
    if (*posp == *lBlockp-1) {
        if (fread16(&checkSum, (size_t) 2, (size_t) 1, fp) != 1) return(-1);
        (*posp)++;
    }

    if (DEBUG) dumpCedarRecord(cedarRecordpp, "getNextCedarBlockedRecord - cedarRecordpp");

    return(0);
}


/***********************************************************************
*
* putNextCedarBlockedRecord   Puts the next CEDAR record into a file
*
*    fp          - File pointer to the Madrigal file
*    cedarRecord - The Cedar record
*    maxBlock    -
*    lbuf        -
*    posp        -
*    block       -
*/
int
putNextCedarBlockedRecord(FILE *fp, Int16 **cedarRecordpp,
                          int *maxBlock,
                          int *lbufp,
                          int *posp,
                          Int16 **blockpp)
{
    int i=0, ltot=0, krec=0;

    if (DEBUG) dumpCedarRecord(cedarRecordpp, "putNextCedarBlockedRecord - cedarRecordpp");

    ltot = (*cedarRecordpp)[0];
    krec = (*cedarRecordpp)[1];

    /* Write the block if the current Cedar record would
       extend it beyond its maximum length */

    if (*lbufp + ltot > *maxBlock && *lbufp > 2) {

        (*blockpp)[0] = *lbufp;                  /* Set length of block */
        (void) setCheckSum (*lbufp, blockpp);    /* Set checksum */
        (void) fwrite16(*blockpp, (size_t) 2, *lbufp, fp);
        /* Reinitialize the block */
        free(*blockpp);
        *blockpp = (Int16 *) NULL;
        *lbufp = 2;
        *posp = 1;
    }

    /* Allocate space for the Cedar record in the block */    
    *lbufp = *lbufp + ltot;
    if (*blockpp == (Int16 *) NULL) {
        *blockpp = (Int16 *)malloc(*lbufp*sizeof(Int16));
    } else {
        *blockpp = (Int16 *)realloc(*blockpp, *lbufp*sizeof(Int16));
    }

    /* Zero out extra words in catalog and header record prologs */
    if (krec == CATALOGBIN) {
        for(i=12; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    } else if (krec == HEADERBIN) {
        for(i=15; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    }

    /* if this is a header or catalog record, need to reorder bytes
       so that fwrite16 does not misorder them */
    if (krec == CATALOGBIN || krec == HEADERBIN) {
        reorderBytes((*cedarRecordpp) + 40, ltot - 40);
    }

    /* Copy the current Cedar record to the block */
    for (i=0; i<ltot; i++) {
        (*blockpp)[*posp] = (*cedarRecordpp)[i];
        (*posp)++;
    }

    /* if this is a header or catalog record, need to 
       return bytes to original order */
    if (krec == CATALOGBIN || krec == HEADERBIN) {
        reorderBytes((*cedarRecordpp) + 40, ltot - 40);
    }

    return(0);
}


/***********************************************************************
*
* flushCedarBlockedRecord   Flushes the last CEDAR record into a CBF file
*
*    fp          - File pointer to the Madrigal file
*    cedarRecord - The Cedar record
*    maxBlock    -
*    lbuf        -
*    posp        -
*    block       -
*
*/
int
flushCedarBlockedRecord(FILE *fp, Int16 **cedarRecordpp,
                        int *maxBlock,
                        int *lbufp,
                        int *posp,
                        Int16 **blockpp)
{

    if (*blockpp == (Int16 *)NULL) {
        return(0);
    }
    (*blockpp)[0] = *lbufp;                  /* Set length of block */
    (void) setCheckSum (*lbufp, blockpp);    /* Set checksum */
    (void) fwrite16(*blockpp, (size_t) 2, *lbufp, fp);
    /* Reinitialize the block */
    free(*blockpp);
    *blockpp = (Int16 *) NULL;
    *lbufp = 1;
    *posp = 1;
   
    return(0);
}


/***********************************************************************
*
* getNextCedarUnblockedRecord   Gets the next CEDAR record from a file
*
*    fp          - File pointer to the Madrigal file
*    cedarRecord - The Cedar record
*
*/
int
getNextCedarUnblockedRecord(FILE *fp, Int16 **cedarRecordpp)
{
    Int16 ltot=0;

    if (*cedarRecordpp != (Int16 *) NULL) {
        free(*cedarRecordpp);
        *cedarRecordpp = (Int16 *) NULL;
    }

    /* Read record length */
    if (fread16(&ltot, (size_t) 2, (size_t) 1, fp) != 1) 
        return(-1);

    /* Allocate space for record */
    *cedarRecordpp = (Int16 *)malloc(ltot*sizeof(Int16));

    /* Read rest of record */
    if (fread16(*cedarRecordpp+1, (size_t) 2, (size_t) (ltot-1), fp) != ltot-1) 
        return(-1);
    (*cedarRecordpp)[0] = ltot;

    /* if this is a header or catalog record, need to reorder bytes
       so that fread16 did not misorder them */
    if ((*cedarRecordpp)[1] == CATALOGBIN || (*cedarRecordpp)[1] == HEADERBIN) {
        reorderBytes((*cedarRecordpp) + 40, (*cedarRecordpp)[0] - 40);
    }

    return(0);
}


/***********************************************************************
*
* putNextCedarUnblockedRecord   Puts the next CEDAR record into a file
*
*    fp          - File pointer to the Madrigal file
*    cedarRecord - The Cedar record
*
*/
int
putNextCedarUnblockedRecord(FILE *fp, Int16 **cedarRecordpp)
{
    int i=0, ltot=0, krec=0;

    ltot = (*cedarRecordpp)[0];
    krec = (*cedarRecordpp)[1];

    /* Zero out extra words in catalog and header record prologs */
    if (krec == CATALOGBIN) {
        for(i=12; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    } else if (krec == HEADERBIN) {
        for(i=15; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    }

    /* if this is a header or catalog record, need to reorder bytes
       so that fwrite16 does not misorder them */
    if ((*cedarRecordpp)[1] == CATALOGBIN || (*cedarRecordpp)[1] == HEADERBIN) {
        reorderBytes((*cedarRecordpp) + 40, (*cedarRecordpp)[0] - 40);
    }

    /* Write Record */
    (void) fwrite16(*cedarRecordpp, (size_t) 2, (size_t) ltot, fp);

    /* if this is a header or catalog record, need to
       put bytes back in right order */
    if ((*cedarRecordpp)[1] == CATALOGBIN || (*cedarRecordpp)[1] == HEADERBIN) {
        reorderBytes((*cedarRecordpp) + 40, (*cedarRecordpp)[0] - 40);
    }

    return(0);
}


/***********************************************************************
*
* getMemNextCedarUnblockedRecord   Gets the next CEDAR record from memory
*
*    cedarFilepp   - The block of memory holding a list of Cedar records
*    cedarRecordpp - The Cedar record to be populated from cedarFilepp
*    posp          - The present number of Int16's already read from cedarFilepp
*    recordpInMem  - Determines whether cedarRecordpp is pointing into cedarFilepp
*                    or separate block of memory on the heap
*
*/
int getMemNextCedarUnblockedRecord(Int16 **cedarFilepp, 
                                   Int16 **cedarRecordpp,
                                   int *posp,
                                   int *recordpInMem)
{
    Int16 ltot=0;

    /* free old cedarRecordpp if appropriate */
    if (*cedarRecordpp != (Int16 *) NULL && !(*recordpInMem)) {
        free(*cedarRecordpp);
        *cedarRecordpp = (Int16 *) NULL;
    }

    ltot = (int) ((*cedarFilepp)[*posp]);
    if (ltot == 0) {
        return(-1);
    }
    *cedarRecordpp = (Int16 *)malloc(ltot*sizeof(Int16));
    (void) memcpy(*cedarRecordpp, *cedarFilepp+*posp, ltot*sizeof(Int16));
    *posp = *posp + ltot;

    /* cedarRecordpp is now not pointing to cedarFilepp */
    *recordpInMem = 0;

    return(0);
}


/***********************************************************************
*
* putMemNextCedarUnblockedRecord   Puts the next CEDAR record into memory
*
*    cedarFilepp   - The block of memory being filled with a list of Cedar records
*    cedarRecordpp - The Cedar record to be appended to cedarFilepp
*    fileSizep     - The present number of bytes in cedarFilepp
*    posp          - The present number of Int16's in cedarFilepp, not
*                    including trailing 0 (see below)
*
*    To indicate this is last record, append Int16 = 0 at end,
*    so ltot will be zero (last record indicator)
*/
int
putMemNextCedarUnblockedRecord(Int16 **cedarFilepp, Int16 **cedarRecordpp,
                               int *fileSizep, int *posp)
{
    int i=0, ltot=0, krec=0;

    krec = (*cedarRecordpp)[1];

    /* Zero out extra words in catalog and header record prologs */
    if (krec == CATALOGBIN) {
        for(i=12; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    } else if (krec == HEADERBIN) {
        for(i=15; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    }

    ltot = (int) ((*cedarRecordpp)[0]);

    if (*posp+ltot+2 > *fileSizep/2) {
        if (*fileSizep == 0) {
            /* allocate one extra Int16 for trailing 0 */
            *cedarFilepp = (Int16 *)malloc(sizeof(Int16)*(ltot+1));
            *fileSizep = sizeof(Int16)*(ltot+1);
        } else {
            *cedarFilepp = (Int16 *)realloc(*cedarFilepp, (2*ltot)+*fileSizep);
            *fileSizep += 2*ltot;
        }
    }
   
    (void) memcpy(*cedarFilepp+((*fileSizep - 2*ltot)/2 - 1), *cedarRecordpp, ltot*sizeof(Int16));

    /* set last Int16 to zero to indicate last record */
    (*cedarFilepp + (((*fileSizep)/2) - 1))[0] = 0;

    *posp = *posp + ltot;

    return(0);
}


/***********************************************************************
*
* putMemFastNextCedarUnblockedRecord   Puts the next CEDAR record into memory with
*                                      fewer realloc calls.  Allocates more memory
*                                      than needed to increase speed.  Is meant to be
*                                      a private method only called from madrecOpen.
*                                      Requires that cedarFilepp be realloc'ed to right
*                                      size after file is fully loaded into memory
*
*    cedarFilepp   - The block of memory being filled with a list of Cedar records
*    cedarRecordpp - The Cedar record to be appended to cedarFilepp
*    fileSizep     - The present number of bytes in cedarFilepp
*    posp          - The present location of Int16 pointer in file
*    memPos        - The present location of Int16 pointer in memory
*
*    To indicate this is last record, append Int16 = 0 at end,
*    so ltot will be zero (last record indicator)
*/
int putMemFastNextCedarUnblockedRecord(Int16 **cedarFilepp, 
                                       Int16 **cedarRecordpp,
                                       int *fileSizep, 
                                       int *posp,
                                       int *memPos)
{
    int i=0, ltot=0, krec=0;

    krec = (*cedarRecordpp)[1];

    /* Zero out extra words in catalog and header record prologs */
    if (krec == CATALOGBIN) {
        for(i=12; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    } else if (krec == HEADERBIN) {
        for(i=15; i<40; i++) {
            (*cedarRecordpp)[i] = 0;
        }
    }

    ltot = (int) ((*cedarRecordpp)[0]);

    if (*memPos+ltot+2 > *fileSizep/2) {
        if (*fileSizep == 0) {
            /* allocate about 500 records worth to start */
            *cedarFilepp = (Int16 *)malloc(sizeof(Int16)*(ltot*500));
            *fileSizep = sizeof(Int16)*(ltot*500);
        } else {
            /* realloc another about 500 records worth */
            *cedarFilepp = (Int16 *)realloc(*cedarFilepp, (2*500*ltot)+*fileSizep);
            *fileSizep += 2*500*ltot;
        }
    }
   
    (void) memcpy(*cedarFilepp+(*memPos), *cedarRecordpp, ltot*sizeof(Int16));

    *memPos = *memPos + ltot;
    *posp = *posp + ltot;

    /* set last Int16 to zero to indicate last record */
    (*cedarFilepp + (*memPos))[0] = 0;

    return(0);
}


/***********************************************************************
*
* editMemNextCedarUnblockedRecord   Gets pointer to the next CEDAR record
*
*    cedarFilepp   - The block of memory holding a list of Cedar records
*    cedarRecordpp - The Cedar record to be editted - will point to somewhere in
*                    cedarFilepp
*    posp          - The record in cedarFilepp for cedarRecordpp to point at
*    recordpInMem  - Determines whether cedarRecordpp is pointing into cedarFilepp
*                    or separate block of memory on the heap
*
*/
int
editMemNextCedarUnblockedRecord(Int16 **cedarFilepp, 
                                Int16 **cedarRecordpp,
                                int *posp,
                                int *recordpInMem)
{
    Int16 ltot=0;

    /* free old cedarRecordpp if appropriate */
    if (*cedarRecordpp != (Int16 *) NULL && !(*recordpInMem)) {
        free(*cedarRecordpp);
        *cedarRecordpp = (Int16 *) NULL;
    }

    ltot = (int) ((*cedarFilepp)[*posp]);
    if (ltot == 0) {
        return(-1);
    }
    *cedarRecordpp = *cedarFilepp + *posp;
    *posp = *posp + ltot;

    /* cedarRecordpp is now pointing into cedarFilepp */
    *recordpInMem = 1;

    return(0);
}


/***********************************************************************
*
* cedarFileType   Gets Cedar File Type
*
*    Supported formats:
*        0 - Madrigal
*        1 - Blocked Binary
*        2 - Cbf
*        3 - Unblocked Binary
*        4 - Ascii
*
*    Supported record types:
*        0 - Catalog
*        1 - Header
*        2 - Data
*
*/

int
cedarFileType(char *fileName, int madrigalBlockSize, int cbfBlockSize)
{
    enum {
        LBUF = 160,                   /* Length of read buffer */
        MADRIGALPROLOG = 3,           /* Position of 1st prolog */
        BLOCKEDBINARYPROLOG = 1,      /* Position of 1st prolog */
        CBFPROLOG = 5,                /* Position of 1st prolog */
        UNBLOCKEDBINARYPROLOG = 0,    /* Position of 1st prolog */
        ASCIIPROLOG = 0               /* Position of 1st prolog */
    };
    int i=0, isAscii=1;
    FILE *fp;
    long pos=0, fileSize=0;
    Int16 ibuf[LBUF/2];
    unsigned char buf[LBUF];

    /* Read enough bytes from beginning of file to ensure that the
       first prologue has been read, regardless of format */
    if ((fp = fopen(fileName, "r")) == (FILE *)NULL) {
        return(-2);
    }
    (void) fread(buf, (size_t) 1, (size_t) LBUF, fp);

    /* Determine file length */
    pos = 0;
    (void) fseek(fp, pos, SEEK_END);
    fileSize = ftell(fp);
    (void) fclose(fp);

    /* Check to see if this is a CEDAR ASCII File */
    for (i=0; i<6*16; i++) {
        if (isdigit(buf[i])==0 && isspace(buf[i])==0) {
            isAscii = 0;
            break;
        }
    }
    buf[LBUF-1] = '\0';
    if (isAscii == 1) {
        (void) sscanf((char *)buf,
            "%hd %hd %hd %hd %hd %hd %hd %hd %hd %hd %hd %hd %hd %hd %hd %hd",
            &ibuf[0], &ibuf[1], &ibuf[2], &ibuf[3],
            &ibuf[4], &ibuf[5], &ibuf[6], &ibuf[7],
            &ibuf[8], &ibuf[9], &ibuf[10], &ibuf[11],
            &ibuf[12], &ibuf[13], &ibuf[14], &ibuf[15]);
        if (isProlog(&ibuf[ASCIIPROLOG])) {
            /* printf("Ascii\n") */;
            return(4);
        } else {
            return(-1);
        }
    }

    /* The file is binary, so determine whether it is one of the four
       supported Cedar binary types */

    /* Endian-independent byte-stream -> 16-bit integer array */
    for (i=0; i<LBUF; i=i+2) {
        ibuf[i/2] = buf[i] << 8;      /* Insert high-order byte */
        ibuf[i/2] |= buf[i+1] & 0xFF; /* Insert low-order byte */
    }
    /*
    for (i=0; i<LBUF/2; i=i++) {
        if (i>0 && 10*(i/10)==i) printf("\n");
        (void) printf("%6d ", ibuf[i]);
    }
    (void) printf("\n");
    */

    if (div(fileSize, madrigalBlockSize).rem == 0 &&   
        isProlog(&ibuf[MADRIGALPROLOG])) {
       /*  printf("Madrigal\n"); */
        return(0);
    } else if (div(fileSize, cbfBlockSize).rem == 0 &&   
               isProlog(&ibuf[CBFPROLOG])) {
        /* printf("Cbf\n"); */
        return(2);
    } else if (isProlog(&ibuf[BLOCKEDBINARYPROLOG])) {
        /* printf("Blocked Binary\n"); */
        return(1);
    } else if (isProlog(&ibuf[UNBLOCKEDBINARYPROLOG])) {
       /* printf("Unblocked Binary\n"); */
        return(3);
    }

    return(-1);
}


/***********************************************************************
*
* isProlog - Checks for consistent Cedar prolog
*   prolog - Pointer to the prolog
*
*/
int
isProlog(Int16 *prolog)
{
    int ltot=0,krec=0,kinst=0,kindat=0,ibyr=0,ibdt=0,ibhm=0,ibcs=0,ieyr=0,iedt=0,
        iehm=0,iecs=0,lprol=0,jpar=0,mpar=0,nrow=0;

    ltot = prolog[0];    /* Length of record */
    krec = prolog[1];    /* Kind of record */
    kinst = prolog[2];   /* Instrument code */
    kindat = prolog[3];  /* Kind-of-data code */
    ibyr = prolog[4];    /* Beginning year */
    ibdt = prolog[5];    /* Beginning date */
    ibhm = prolog[6];    /* Beginning hour and minute */
    ibcs = prolog[7];    /* Beginning centisecond */
    ieyr = prolog[8];    /* Ending year */
    iedt = prolog[9];    /* Ending date */
    iehm = prolog[10];   /* Ending hour and minute */
    iecs = prolog[11];   /* ending centisecond */
    lprol = prolog[12];  /* Length of prologue */
    jpar = prolog[13];   /* Number of single-valued parameters */
    mpar = prolog[14];   /* Number of multiple-valued parameters */
    nrow = prolog[15];   /* Number of entries for each multiple-valued parameter */

    if (krec!=2001 && krec!=3002 && krec!=1002 &&
         krec!=2101 && krec!=3101 && krec!=1101) {
        /* printf("is not prolog 1\n"); */
	return(0);
    }

    if (kinst < 1) {
        return(0);
    }

    if (kindat < 1) {
        return(0);
    }

    if (ibhm < 0) {
        return(0);
    }

    if (ibcs < 0) {
        return(0);
    }

    if (iehm < 0) {
        return(0);
    }

    if (iecs < 0) {
        return(0);
    }
    
   

    if (ieyr<ibyr || (ieyr==ibyr && iedt<ibdt)) {
        /* printf("is not prolog 2\n"); */
	return(0);
    }

    if (krec==1002 && ltot!=lprol+2*jpar+mpar*(nrow+1)) {
        /* printf("is not prolog 3\n"); */
	return(0);
    }

    if (krec==1101 && ltot!=1+((jpar+19)/20)*2+((mpar+19)/20)*(nrow+1)) {
        /* printf("is not prolog 4\n"); */
	return(0);
    }

    /* printf("is prolog\n"); */
    return(1);
}


/***********************************************************************
*
*/
int
madptr(Int16 *time)
{
    int n1jan50=2433283,year=0,month=0,day=0,hour=0,minute=0,
        second=0,im1=0,iyr=0,imd=0,ihm=0,ics=0;

    iyr = time[0];
    imd = time[1];
    ihm = time[2];
    ics = time[3];
    year = iyr;
    month = imd/100;
    day = imd - 100*month;
    hour = ihm/100;
    minute = ihm - 100*hour;
    second = ics/100;
    im1 = (jday1(day, month, year) - n1jan50)*86400 +
          hour*3600 + minute*60 + second;
    return (im1);
}


/***********************************************************************
*
* 
*
*/
int
jday1(int day, int month, int year)
{

    int jday1no=0, y=0, c=0, ya=0, m=0;

    if (idmyk1(day, month, year) != 0) return(-1);

    m = month;
    if (m > 2) {
        m = month - 3;
        y = year;
    } else {
        m = month + 9;
        y = year - 1;
    }
    c = y/100;
    ya = y - 100*c;
    jday1no = (146097*c)/4+(1461*ya)/4 + (153*m + 2)/5 + day + 1721119;
    return(jday1no);
}



/***********************************************************************
*
* 
*
*/
int
idmyk1(int day, int month, int year)
{

    int l=0;
    int numday[12] = {31,28,31,30,31,30,31,31,30,31,30,31};

    if (day < 1 || month < 1 || month > 12 || year < 0 || year > 9999) {
        return(1);
    }

    if (month == 2 && year/4*4 == year &&
        (year/400*400 == year || year/100*100 != year))
        l = 1;
    else {
        l = 0;
    }

    if (day > numday[month-1]+l)
        return(1);

    return(0);
}


/***********************************************************************
*
* setCheckSum   sets block checksum
*
*/

int
setCheckSum (int blockSize, Int16 **blockpp)
{
    int i=0;
    Int16 sum=0;

    sum = 0;
    for (i=0; i<blockSize-1; i++) {
        sum = sum^(*blockpp)[i];
    }
    (*blockpp)[blockSize-1] = sum;
    return(0);
}


/***********************************************************************
*
* decodeBits    Returns bits b1 to b2 of buf as an unsigned integer
*
*/

unsigned int
decodeBits(unsigned char *buf, unsigned int b1, unsigned int b2)
{
    unsigned char vc[4];
    unsigned int b=0, bv=0, s=0, val=0;
    unsigned int getbit(unsigned char *, unsigned int);
    void setbit(unsigned char *, unsigned int, unsigned int);

    vc[0] = 0;
    vc[1] = 0;
    vc[2] = 0;
    vc[3] = 0;
    s = 32;

    for (b=b1; b<=b2; b++) {
        bv = getbit(buf, b);
        setbit(vc, (unsigned int)(s-1+b-b2), bv);
    }

    val = vc[0] << 24;
    val |= vc[1] << 16;
    val |= vc[2] << 8;
    val |= vc[3];
    
    return(val);
}


/***********************************************************************
*
* encodeBits    Encodes unsigned integer val in bits b1 to b2 of buf
*
*/

void
encodeBits(unsigned char *buf, unsigned int b1, unsigned int b2, unsigned int val)
{
    unsigned char vc[4];
    unsigned int b=0, bv=0, s=0;
    unsigned int getbit(unsigned char *, unsigned int);
    void setbit(unsigned char *, unsigned int, unsigned int);

    vc[0] = val >> 24;
    vc[1] = val >> 16;
    vc[2] = val >> 8;
    vc[3] = val;

    s = 8*sizeof(unsigned int);

    for (b=b1; b<=b2; b++) {
        bv = getbit(vc, s-1+b-b2); 
        setbit(buf, b, bv);
    }
    
    return;
}


/***********************************************************************
*
* getbit    returns 1 if bit b in array buf is 1, else 0.
*
*/

unsigned int
getbit(unsigned char *buf, unsigned int b)
{
    unsigned int byte=0, pos=0, bv=0;

    byte = b/8;
    pos = b - 8*byte;
    bv = (buf[byte]>>(7-pos)) & 1;

    return(bv);
}


/***********************************************************************
*
* setbit    Sets bit b in array buf to last bit in bv.
*           Thus, if bv=0, bit b in buf will be set to 0,
*            else if bv=1, bit b in buf will be set to 1.
*           No other bit in buf will be changed.
*
*/

void
setbit(unsigned char *buf, unsigned int b, unsigned int bv)
{
    unsigned int byte=0, pos=0;

    byte = b/8;
    pos = b - 8*byte;
    buf[byte] = (bv&1)<<(7-pos) | (buf[byte] & ~((bv&1)<<(7-pos)));

    return;
}


/***********************************************************************
*
* dumpCedarRecord    Dumps beginning and end of Cedar record
*
*/

void
dumpCedarRecord(Int16 **recordpp, char *title)
{
    int i=0;

    (void) printf("%s\n", title);
    for (i=0; i<(*recordpp)[0]; i++) {
        if (i < 50 || i > (*recordpp)[0]-30) {
            (void) printf("i,record[i] = %6d %6d\n", i, (*recordpp)[i]);
        }
    }
}


/***********************************************************************
*
* fread16   Reads big-endian 16-bit integers
*
*    ptr           - Pointer to array of 16-bit integers
*    size_t size   - Must be 2
*    size_t nitems - Number of 16-bit integers to be read
*    stream        - Pointer to input file. The file should be
*                    positioned at the beginning of an sequence of at
*                    least nitems big-endian 16-bit integers.
*
*    The CEDAR format represents data stored on tape or disk as 16-bit big
*    endian integers. fread16 is endian-neutral. It works on both big endian
*    and little endian computers. However, this flexibility imposes a
*    performance penalty on big endian computers. This penalty can be
*    reduced by changing the BIGENDIAN constant to 1.
*
*/

size_t
fread16(void *ptr, size_t size, size_t nitems, FILE *stream)
{
    int i=0, ret=0;
    Int16 *i16;
    unsigned char i8[2];
    const int BIGENDIAN=0;

    if(BIGENDIAN) {
        return(fread(ptr, size, nitems, stream));
    }

    if (size != 2) {
        ret = -1;
        return((size_t)ret);
    }

    /* Read big-endian 16-bit integers */
    ret = (int) fread(ptr, 2, nitems, stream);

    /* Convert the big-endian integers into 16-bit integers on this machine */
    i16 = ptr;
    for (i=0; i<2*nitems; i=i+2) {
        i8[0] = *((unsigned char *)ptr + i);
        i8[1] = *((unsigned char *)ptr + i+1);
        i16[i/2] = i8[0] << 8;       /* Insert high-order byte */
        i16[i/2] |= i8[1] & 0xFF;    /* Insert low-order byte */
        /*
        (void) printf("i,i8[0],i8[1],i16[i/2],i16[i/2] = %d %hx %hx %hx %d\n", 
            i,i8[0],i8[1],i16[i/2],i16[i/2]);
        */
    }

    return(ret);
}


/***********************************************************************
*
* fwrite16   Writes big-endian 16-bit integers   
*
*    ptr           - Pointer to array of 16-bit integers
*    size_t size   - Must be 2
*    size_t nitems - Number of 16-bit integers to write
*    stream        - Pointer to input file. Nitems 16-bit integers will
*                    be written to stream in big-endian order.
*
*    The CEDAR format represents data stored on tape or disk as 16-bit big
*    endian integers. fread16 is endian-neutral. It works on both big endian
*    and little endian computers. However, this flexibility imposes a
*    performance penalty on big endian computers. This penalty can be
*    reduced by changing the BIGENDIAN constant to 1.
*
*/

size_t
fwrite16(void *ptr, size_t size, size_t nitems, FILE *stream)
{
    int i=0, ret=0;
    Int16 *i16;
    unsigned char i8[2];
    const int BIGENDIAN=0;

    if(BIGENDIAN) {
        return(fwrite(ptr, size, nitems, stream));
    }

    if (size != 2) {
        ret = -1;
        return((size_t)ret);
    }

    i16 = ptr;
    for (i=0; i<nitems; i++) {
        i8[0] = i16[i] >> 8;         /* Extract high-order byte */
        i8[1] = i16[i] & 0xFF;       /* Extract low-order byte */
        ret = fwrite(&i8, 1, 2, stream);
    }

    return(ret);
}


/***********************************************************************
*
* reorderBytes   returns byte order of original file
*
*    ptr           - Pointer to Int16 array 
*    numInt16s     - Size of ptr Int16 array 
*
*    orderBytes undoes the effect of using fread16, and returns an array of
*    chars read via fread16 to its original order as found in the file.  This is
*    used in reading header and catalog records, where the data is read as chars
*    and not as Int16's.  For big-endian machines it does nothing, for little-endian
*    machines it switches adjacent bytes.
*
*/
void reorderBytes(Int16 * ptr, int numInt16s)
{
    int i;
    unsigned char i8[2];

    for (i = 0; i < 2 * numInt16s; i=i+2)
    {
        /* Convert the integers on this machine into original big-endian */
        i8[0] = *((unsigned char *)ptr + i);
        i8[1] = *((unsigned char *)ptr + i+1);
        ptr[i/2] = i8[0] << 8;       /* Insert high-order byte */
        ptr[i/2] |= i8[1] & 0xFF;    /* Insert low-order byte */
    }
}
