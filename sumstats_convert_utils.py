import sys, os, re, logging, datetime
import numpy as np
import pandas as pd
import gzip
import six
import itertools
from collections import namedtuple

Cols = namedtuple('Cols', ['SNP', 'CHR', 'BP', 'PVAL', 'A1', 'A2', 'N', 'NCAS', 'NCON', 'Z', 'OR', 'BETA', 'LOGODDS', 'SE', 'INFO', 'FRQ', 'NSTUDY', 'CHRPOS'])
cols = Cols._make(        ['SNP', 'CHR', 'BP', 'PVAL', 'A1', 'A2', 'N', 'NCAS', 'NCON', 'Z', 'OR', 'BETA', 'LOGODDS', 'SE', 'INFO', 'FRQ', 'NSTUDY', 'CHRPOS'])

null_values = {
    cols.LOGODDS: 0,
    cols.BETA: 0,
    cols.OR: 1,
    cols.Z: 0
}

default_cnames = {

    # RS NUMBER
    'SNP': cols.SNP,
    'MARKERNAME': cols.SNP,
    'SNPID': cols.SNP,
    'RS': cols.SNP,
    'RSID': cols.SNP,
    'RS_NUMBER': cols.SNP,
    'RS_NUMBERS': cols.SNP,
    # CHROMOSOME
    'CHR': cols.CHR,
    'CHROMOSOME' : cols.CHR,
    # POSITION
    'POS': cols.BP,
    'BP': cols.BP,
    'POSITION' : cols.BP,
    # NUMBER OF STUDIES
    'NSTUDY': cols.NSTUDY,
    'N_STUDY': cols.NSTUDY,
    'NSTUDIES': cols.NSTUDY,
    'N_STUDIES': cols.NSTUDY,
    # P-VALUE
    'P': cols.PVAL,
    'PVALUE': cols.PVAL,
    'P_VALUE':  cols.PVAL,
    'PVAL': cols.PVAL,
    'P_VAL': cols.PVAL,
    'GC_PVALUE': cols.PVAL,
    # ALLELE 1
    'A1': cols.A1,
    'ALLELE1': cols.A1,
    'ALLELE_1': cols.A1,
    'EFFECT_ALLELE': cols.A1,
    'REFERENCE_ALLELE': cols.A1,
    'INC_ALLELE': cols.A1,
    'EA': cols.A1,
    # ALLELE 2
    'A2': cols.A2,
    'ALLELE2': cols.A2,
    'ALLELE_2': cols.A2,
    'OTHER_ALLELE': cols.A2,
    'NON_EFFECT_ALLELE': cols.A2,
    'NON_EFF_ALLELE': cols.A2,
    'DEC_ALLELE': cols.A2,
    'NEA': cols.A2,
    # N
    'N': cols.N,
    'NCASE': cols.NCAS,
    'CASES_N': cols.NCAS,
    'N_CASE': cols.NCAS,
    'N_CASES': cols.NCAS,
    'N_CONTROLS': cols.NCON,
    'N_CAS': cols.NCAS,
    'N_CON': cols.NCON,
    'N_CASE': cols.NCAS,
    'NCONTROL': cols.NCON,
    'CONTROLS_N': cols.NCON,
    'N_CONTROL': cols.NCON,
    'WEIGHT': cols.N,  # metal does this. possibly risky.
    # SIGNED STATISTICS
    'ZSCORE': cols.Z,
    'Z-SCORE': cols.Z,
    'GC_ZSCORE': cols.Z,
    'Z': cols.Z,
    'OR': cols.OR,
    'B': cols.BETA,
    'BETA': cols.BETA,
    'LOG_ODDS': cols.LOGODDS,
    'EFFECTS': cols.BETA,
    'EFFECT': cols.BETA,
    'SIGNED_SUMSTAT': 'SIGNED_SUMSTAT',
    # STANDARD ERROR
    'SE' : cols.SE,
    'STDERR' : cols.SE,
    # INFO
    'INFO': cols.INFO,
    # MAF
    'EAF': cols.FRQ,
    'FRQ': cols.FRQ,
    'MAF': cols.FRQ,
    'FRQ_U': cols.FRQ,
    'F_U': cols.FRQ,
}

describe_cname = {
    cols.SNP: 'Variant ID (e.g., rs number)',
    cols.CHR: 'Chromosome number',
    cols.BP: 'Base-pair position',
    cols.PVAL: 'p-Value',
    cols.A1: 'Allele 1, interpreted as ref allele for signed sumstat.',
    cols.A2: 'Allele 2, interpreted as non-ref allele for signed sumstat.',
    cols.N: 'Sample size',
    cols.NCAS: 'Number of cases',
    cols.NCON: 'Number of controls',
    cols.Z: 'Z-score (0 --> no effect; above 0 --> A1 is trait/risk increasing)',
    cols.OR: 'Odds ratio (1 --> no effect; above 1 --> A1 is risk increasing)',
    cols.BETA: '[linear/logistic] regression coefficient (0 --> no effect; above 0 --> A1 is trait/risk increasing)',
    cols.LOGODDS: 'Log odds ratio (0 --> no effect; above 0 --> A1 is risk increasing)',
    cols.SE: 'standard error of the effect size',
    cols.INFO: 'INFO score (imputation quality; higher --> better imputation)',
    cols.FRQ: 'Allele frequency',
    'SIGNED_SUMSTAT': 'Directional summary statistic as specified by --signed-sumstats.',
    cols.NSTUDY: 'Number of studies in which the SNP was genotyped.',
    'UNKNOWN': 'Unknown column type (will be skipped).',
    cols.CHRPOS: 'chr:pos column with colon-separated information about Chromosome and Base-pair position',
}

def clean_header(header):
    '''
    For cleaning file headers.
    - convert to uppercase
    - replace dashes '-' with underscores '_'
    - replace dots '.' (as in R) with underscores '_'
    - remove newlines ('\n')
    '''
    return header.upper().replace('-', '_').replace('.', '_').replace('\n', '')

def format_chr(chrvec):
    '''
    Reformat chromosome names.

    Input:
    ------
    Vector of chromosome IDs

    Output:
    -------
    Vector of cleaned chromosome IDs

    Note:
    * Remove "chr/Chr/CHR/MT/mt" strings in the name
    * Change chrX to 23, ChrY to 24, MT to 25
    '''
    try:
        chrvec = chrvec.astype('str')
        tmpchrvec = chrvec.str.replace('[chrCHR]', '', case=False)
        tmpchrvec[tmpchrvec=='X'] = '23'
        tmpchrvec[tmpchrvec=='x'] = '23'
        tmpchrvec[tmpchrvec=='Y'] = '24'
        tmpchrvec[tmpchrvec=='y'] = '24'
        tmpchrvec[tmpchrvec=='M'] = '25'
        tmpchrvec[tmpchrvec=='m'] = '25'
        tmpchrvec[tmpchrvec=='MT'] = '25'
        tmpchrvec[tmpchrvec=='mt'] = '25'
        # TO-DO: Bellow is anoying
        tmpchrvec[tmpchrvec=='NA'] = '-9'
        tmpchrvec[tmpchrvec.isnull()] = '-9'
        tmpchrvec[tmpchrvec=='nan'] = '-9'
        tmpchrvec[tmpchrvec==' '] = '-9'
        tmpchrvec = tmpchrvec.astype('float').astype('int')
        return tmpchrvec
    except:
        raise

def print_header(fh, lines=5):
    (openfunc, _) = get_compression(fh)
    with openfunc(fh) as f:
        for line in itertools.islice(f, lines):
            line = line if isinstance(line, six.string_types) else line.decode('utf-8')
            print(line.rstrip('\n'))

def get_compression_and_open(fh):
    (openfunc, _) = get_compression(fh)
    return openfunc(fh)

def get_compression(fh):
    '''
    Read filename suffixes and figure out whether it is gzipped,bzip2'ed or not compressed
    '''
    if fh.endswith('gz'):
        compression = 'gzip'
        openfunc = gzip.open
    elif fh.endswith('bz2'):
        compression = 'bz2'
        openfunc = bz2.BZ2File
    else:
        openfunc = open
        compression = None

    return openfunc, compression
