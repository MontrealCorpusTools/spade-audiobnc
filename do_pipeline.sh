#!/bin/bash
PREFIX=/home/linguistics/mgooda2/pipeline/
CORPUS_DIR=corpus_for_mfa
PRONUNCIATION_DICTIONARY=pronunciation.txt
MFA_DIR=/home/linguistics/mgooda2/montreal-forced-aligner/bin

mkdir -p corpus_for_mfa output cleaned_textgrids classify_grids speakered_textgrids_chunked out_with_labels
rm corpus_for_mfa/*
rm pronunciation.txt
python3 output_dictionary.py $(ls input/ | sed 's/^/textgrid\//')
python3 output_mfa_formatted.py $(ls input/ | sed 's/^/textgrid\//')
cd $MFA_DIR
./mfa_align $PREFIX$CORPUS_DIR $PREFIX$PRONUNCIATION_DICTIONARY english $PREFIX/output -n -j 20
cd $PREFIX
python3 aligner-difference.py
python3 classify.py $(find classify_grids -type f)
python3 speaker_data.py $(find out_with_labels -type f)
python3 reduced_data_set.py $(find speakered_textgrids_chunked -type f)
