#!/bin/bash

############################################################
# HELP
############################################################

# Help()
# {
#    # Display Help
#    echo "Add description of the script functions here."
#    echo
#    echo "Syntax: scriptTemplate [-g|h|v|V]"
#    echo "options:"
#    echo "g     Print the GPL license notification."
#    echo "h     Print this Help."
#    echo "v     Verbose mode."
#    echo "V     Print software version and exit."
#    echo
# }

############################################################
# PARSING ARGUMENTS
############################################################

# while getopts ":ht:" option; do
#     case $option in
#         h)
#             Help
#             exit;;
#         t)
#             Threads=$OPTARG;;
#        \?)
#             echo "Error: Invalid option"
#             exit;;
#     esac
# done

############################################################
# TURBOPREP!
############################################################

START=$(date +%s.%N)
ITK_GET_GLOBAL_DEFAULT_NUMBER_OF_THREADS=$Threads

# Step 1: Bias field correction
N4BiasFieldCorrection -d 3 \
                      -i $1 \
                      -o $2/corrected.nii.gz \
                      -s 3 \
                      -v

# Step 2: Affine registration to template space
antsRegistrationSyNQuick.sh -d 3 \
                            -f $3 \
                            -m $2/corrected.nii.gz \
                            -o $2/ants_ \
                            -n 12 -t a

# Step 3: Fast semantic segmentation
mri_synthseg --i $2/ants_Warped.nii.gz \
             --o $2/segm.nii.gz \
             --fast \
             --threads 12

# Step 4: Extrapolating brain mask from segmentation
mri_threshold -B 1 \
              $2/segm.nii.gz \
              2 \
              $2/mask.nii.gz

# Step 5: Intensity normalization
ws-normalize -m $2/mask.nii.gz \
             -o $2/normalized.nii.gz \
             -mo $4 \
             $2/ants_Warped.nii.gz

END=$(date +%s.%N)
DIFF=$(echo "$END - $START" | bc)
echo "turboprep | elapsed time: $DIFF"