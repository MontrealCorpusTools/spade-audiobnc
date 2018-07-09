To reproduce the dataset, all that's necessary is placing the requested
textgrids in the `input` directory. You must have a symbolic link(or
just a directory) to both the wav and textgrids directories, labeled
`wavs` and `textgrid` respectively. It is also necessary to change the
directory names at the top of the following
scripts:`do_pipeline.sh, aligner_difference.py, speaker_data.py`.
`PREFIX` should be changed to wherever you have put the pipeline folder,
`MFA_DIR` should point to a directory containing the `mfa_align` binary
for MFA. `AUDIO_BNC_DIR` should point to wherever the `Texts` directory
of the BNC is located. Then, simply run the `do_pipeline` script, this
will take a considerable amount of time(upwards of 24 hours) to run on
the overall corpus.

Script description
------------------

1.  `output_dictionary.py`: Runs over all textgrids and generates
    `pronunciation.txt` containing all words and their pronunciations
    for MFA.

2.  `output_mfa_formatted.py`: Runs over all textgrids and replaces with
    labeled utterances for use in MFA. Also cuts each wav file to just
    the part used in a given textgrid again for MFA.

3.  `aligner-difference.py`: Calculates HNR and aligner-difference for
    all textgrids in `output`

4.  `classify.py`: Goes over textgrids outputted by
    `aligner-differenc.py` and decides whether to classify them as good
    or bad based on the previously described classifier.

5.  `speaker_data.py`: Splits output from `classify.py` into speaker
    tiers based on the XML transcripts.

6.  `reduced_data_set.py`: Goes over output from `speaker_data.py` and
    deletes all utterances not labeled "good". Additionally deletes
    tiers containing feature values.

Directory description
---------------------

1.  `requirements.txt`: List of required pip packages in python, to
    install run `pip install -r requirements.txt`

2.  `pronunciation.txt`: List of pronunciations for all words in
    AudioBNC for MFA.

3.  `input`: A directory with all the AudioBNC textgrids you wish to
    clean.

4.  `wavs`: Directory or symlink to directory of all the AudioBNC wavs.

5.  `textgrid`: Directory or symlink to directory of all the AudioBNC
    TextGrids.

6.  `output`: Output from MFA

7.  `classify_grids`: Output from `aligner-difference.py`, TextGrids
    which have yet to be classified.

8.  `corpus_for_mfa`: Directory containing TextGrids to be used by MFA.

9.  `out_with_labels`: Classified textgrids which have not yet been
    speakerised.

10. `speakered_textgrids_chunked`: Cleaned textgrids with labels
    describing quality of utterances, split into speaker tiers. Still
    contains all data, included feature-tiers.

11. `cleaned_textgrids`: Final product of pipeline, to be used in SPADE.
    Includes "good" utterances split into speaker-tiers.

