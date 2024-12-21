# Create the directory if it doesn't exist
mkdir -p software

# Download Freesurfer if it doesn't already exist
if [ ! -f software/freesurfer.tar.gz ]; then
    wget -O software/freesurfer.tar.gz \
        https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/7.4.1/freesurfer-linux-centos7_x86_64-7.4.1.tar.gz
fi

# Download ANTs if it doesn't already exist
if [ ! -f software/ants.zip ]; then
    wget -O software/ants.zip \
        https://github.com/ANTsX/ANTs/releases/download/v2.4.3/ants-2.4.3-centos7-X64-gcc.zip
fi

# Download Miniconda if it doesn't already exist
if [ ! -f software/miniconda.sh ]; then
    wget -O software/miniconda.sh \
        https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
fi