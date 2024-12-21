#!/bin/bash

tar -xvzf software/freesurfer.tar.gz

mkdir freesurfer_minified
mkdir freesurfer_minified/bin
mkdir freesurfer_minified/models
cp -R freesurfer/python freesurfer_minified/python
cp -R freesurfer/models/synthseg* freesurfer_minified/models
cp -R freesurfer/models/synthstrip* freesurfer_minified/models
cp -R freesurfer/bin/mri_synthseg freesurfer_minified/bin
cp -R freesurfer/bin/mri_synthstrip freesurfer_minified/bin
cp -R freesurfer/bin/fspython freesurfer_minified/bin
tar -czvf freesurfer-minified.tar.gz freesurfer_minified/
mv freesurfer-minified.tar.gz software/

rm -r freesurfer
rm -r freesurfer_minified
rm software/freesurfer.tar.gz