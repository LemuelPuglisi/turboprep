# Docker instructions


## Building the docker image

Download the required softwares (`freesurfer`, `ANTs` and `anaconda`). 

```bash
bash download.sh
```

Since we only need `mri_synthseg` and `mri_synthstrip` commands from `freesurfer`, we can filter out all the other binaries and models. Run the following as root:

```bash
bash reduce-freesurfer.sh
```

Finally, build the Docker container:

```bash
docker build -t lemuelpuglisi/turboprep .
```

This is a `cpu` version of turboprep. Hopefully, a gpu version will come next. If you need to preprocess a lot of data, I strongly suggest to run the local version of turboprep (see the main README). 
