import os
import argparse
import nibabel as nib
from tqdm import tqdm

NPROC = os.cpu_count()

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs',                  type=str, required=True,  help='text file where each line is the path of an image to process')
    parser.add_argument('--outputs',                 type=str, required=True,  help='text file where each line is the path to an output')
    parser.add_argument('--template',                type=str, required=True,  help='path of template image')
    parser.add_argument('-m', '--modality',          type=str, default='t1',   help='Modality {t2,other,md,t1,pd,flair} (default is t1)')
    parser.add_argument('-t', '--threads',           type=int, default=NPROC,  help='Threads (default: number of cores)')
    parser.add_argument('-s', '--shrink-factor',     type=int, default=3,      help='Bias field correction shrink factor (default: 3), see N4BiasFieldCorrection')
    parser.add_argument('-r', '--registration-type', type=str, default='a',    help='Registration type {t,r,a} (default is \'a\' (affine), see antsRegistrationSyNQuick.sh)')
    parser.add_argument('--no-bfc',                  type=str,                 help='text file listing the inputs for which to skip bias field correction')
    parser.add_argument('--keep',                    action='store_true',      help='Keep intermediate files')

    args = parser.parse_args()
    inp_file = args.inputs
    out_file = args.outputs
    nbc_file = args.no_bfc
    template = args.template

    modality = args.modality
    threads  = args.threads
    shrinkf  = args.shrink_factor
    regtype  = args.registration_type
    keepint  = args.keep

    assert os.path.exists(inp_file), 'input file doesn\'t exist'
    assert os.path.exists(out_file), 'output file doesn\'t exist'
    assert os.path.exists(template), 'template image file doesn\'t exist'
    assert nbc_file is None or os.path.exists(nbc_file), 'no-bfc file doesn\'t exist'

    with open(inp_file, 'r') as f:
        inp_list = [ l.strip() for l in f.readlines() ]

    with open(out_file, 'r') as f:
        out_list = [ l.strip() for l in f.readlines() ]

    nbc_list = set()
    if nbc_file is not None:
        with open(nbc_file, 'r') as f:
            nbc_list = set([ l.strip() for l in f.readlines() ])

    inp_out_pairs = zip(inp_list, out_list)
    reg_seg_pairs = []

    #######################################################
    # Bias field correction and registration to template  #
    #######################################################

    for inp_path, out_path in tqdm(inp_out_pairs, total=len(inp_list)):
        
        if not os.path.exists(inp_path):
            print('File not exists, skipping', inp_path)
            continue

        if not os.path.exists(out_path):
            os.makedirs(out_path)

        corrected_path = inp_path
        if inp_path not in nbc_list:
            # apply bias field correction.
            corrected_path = os.path.join(out_path, 'corrected.nii.gz')
            os.system(f"N4BiasFieldCorrection -d 3 -i {inp_path} -o {corrected_path} -s {shrinkf} -v  > /dev/null")

        reg_output = os.path.join(out_path, 'turboprep_')
        os.system('antsRegistrationSyNQuick.sh -d 3 '
                  f'-f {template} -m {corrected_path} ' 
                  f'-o {reg_output} -n {threads} '
                  f'-t {regtype}  > /dev/null')

        if not keepint:
            os.remove(os.path.join(out_path, 'turboprep_InverseWarped.nii.gz'))
            if corrected_path != inp_path: os.remove(corrected_path)
        
        os.rename(os.path.join(out_path, 'turboprep_0GenericAffine.mat'),
                  os.path.join(out_path, 'affine_transf.mat'))

        reg_path = os.path.join(out_path, 'turboprep_Warped.nii.gz')
        reg_seg_pairs.append((reg_path, os.path.join(out_path, 'segm.nii.gz')))

    
    #######################################################
    # Semantic segmentation with SynthSeg                 #
    #######################################################

    with open('temp-input.txt', 'w') as f:
        for reg, _ in reg_seg_pairs:
            f.write(reg + '\n')

    with open('temp-output.txt', 'w') as f:
        for _, out in reg_seg_pairs:
            f.write(out + '\n')

    os.system('mri_synthseg '
              f'--i temp-input.txt ' 
              f'--o temp-output.txt '
              f'--fast '
              f'--threads {threads}')

    os.remove('temp-input.txt')
    os.remove('temp-output.txt')

    #######################################################
    # Brain extraction and intensity normalization         #
    #######################################################

    for reg_path, seg_path in tqdm(reg_seg_pairs):
        
        output_dir = os.path.dirname(seg_path)
        mask_path = os.path.join(output_dir, 'mask.nii.gz')
        norm_path = os.path.join(output_dir, 'normalized.nii.gz')

        os.system(f'mri_threshold -B 1 {seg_path} 2 {mask_path} > /dev/null')
        os.system(f'ws-normalize -m {mask_path} -o {norm_path} -mo {modality} {reg_path} > /dev/null')

        if not keepint:
            os.remove(reg_path)

        smri = nib.load(norm_path)
        mask = nib.load(mask_path).get_fdata().round()
        smri_arr = smri.get_fdata()
        smri_arr[mask == 0] = smri_arr.min()        
        brain = nib.Nifti1Image(smri_arr, smri.affine, smri.header)
        nib.save(brain, os.path.join(output_dir, 'brain.nii.gz'))