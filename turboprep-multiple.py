import os
import argparse
import numpy as np
import nibabel as nib
from multiprocessing import Pool
from tqdm import tqdm
from intensity_normalization.normalize.whitestripe import WhiteStripeNormalize
from intensity_normalization.typing import Modality

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

    print('🚀 reading input files')

    with open(inp_file, 'r') as f:
        inp_list = [ l.strip() for l in f.readlines() ]

    with open(out_file, 'r') as f:
        out_list = [ l.strip() for l in f.readlines() ]

    nbc_list = set()
    if nbc_file is not None:
        with open(nbc_file, 'r') as f:
            nbc_list = set([ l.strip() for l in f.readlines() ])


    print('🚀 creating output dictionary')

    outputs_dict = {}
    for input_path, output_path in tqdm(zip(inp_list, out_list), total=len(inp_list)):

        if not os.path.exists(input_path):
            print('file', input_path, 'does not exists.')
            continue
        elif not os.path.exists(output_path):
            os.makedirs(output_path)

        outputs_dict[input_path] = {
            'bias_field_correction':    os.path.join(output_path, 'corrected.nii.gz'),
            'skull_stripping':          os.path.join(output_path, 'skullstrip.nii.gz'),
            'ants_prefix':              os.path.join(output_path, 'turboprep_'),
            'affine_registration':      os.path.join(output_path, 'turboprep_Warped.nii.gz'), 
            'semantic_segmentation':    os.path.join(output_path, 'segm.nii.gz'),
            'brain_mask_extraction':    os.path.join(output_path, 'mask.nii.gz'), 
            'intensity_normalization':  os.path.join(output_path, 'normalized.nii.gz'), 
            'brain_extraction':         os.path.join(output_path, 'brain.nii.gz')
        }

        if input_path in nbc_list:
            outputs_dict[input_path]['bias_field_correction'] = input_path

    #######################################################################
    # Bias-field correction + skull stripping + registration to template  #
    #######################################################################

    print('🚀 Bias-field correction + skull stripping + registration to template')

    for input_path in tqdm(list(outputs_dict.keys())):

        input_outputs = outputs_dict[input_path]
        corrected_path  = input_outputs['bias_field_correction']
        skullstrip_path = input_outputs['skull_stripping']
        registered_path = input_outputs['affine_registration']
        registered_pref = input_outputs['ants_prefix']
        brain_path = input_outputs['brain_extraction']

        if os.path.exists(registered_path) or os.path.exists(brain_path):
            # if the registered path exists, then we have already done 
            # this step. If does not exists, then we could have performed 
            # the brain extraction, after which the registered scan id
            # removed, so check for the file with the brain extracted.
            continue


        if input_path != corrected_path:
            os.system('N4BiasFieldCorrection -d 3 '
                     f'-i {input_path} ' 
                     f'-o {corrected_path} '
                     f'-s {shrinkf} -v > /dev/null')

        if not os.path.exists(corrected_path):
            print('N4 correction has failed.')
            del outputs_dict[input_path]
            continue

        os.system(f'mri_synthstrip -i {corrected_path} '
                  f'-o {skullstrip_path} ' 
                  f'--gpu > /dev/null')
        
        if not os.path.exists(skullstrip_path):
            print('Skull stripping has failed.')
            del outputs_dict[input_path]
            continue

        os.system('antsRegistrationSyNQuick.sh -d 3 '
                  f'-f {template} -m {skullstrip_path} ' 
                  f'-o {registered_pref} -n {threads} '
                  f'-t {regtype} > /dev/null')
        
        if not os.path.exists(registered_path):
            print('Affine registration has failed.')
            del outputs_dict[input_path]
            continue

        else:
            if not keepint:
                os.remove(skullstrip_path)
                os.remove(registered_pref + 'InverseWarped.nii.gz')
                if corrected_path != input_path: os.remove(corrected_path)
            os.rename(registered_pref + '0GenericAffine.mat', 
                      os.path.join(os.path.dirname(registered_pref), 'affine_transf.mat'))


    #######################################################
    # Semantic segmentation with SynthSeg                 #
    #######################################################

    print('🚀 semantic segmentation using SynthSeg')

    reg_seg_pairs = []
    for input_path, input_dict in outputs_dict.items():
        reg_path = input_dict['affine_registration']
        seg_path = input_dict['semantic_segmentation']
        if not os.path.exists(seg_path):
            reg_seg_pairs.append((reg_path, seg_path))

    if len(reg_seg_pairs) > 0:

        if os.path.exists('temp-input.txt'):  os.remove('temp-input.txt')
        if os.path.exists('temp-output.txt'): os.remove('temp-output.txt')

        with open('temp-input.txt', 'w') as f:
            for reg, _ in reg_seg_pairs:
                f.write(reg + '\n')

        with open('temp-output.txt', 'w') as f:
            for _, seg in reg_seg_pairs:
                f.write(seg + '\n')

        os.system('mri_synthseg '
                f'--i temp-input.txt ' 
                f'--o temp-output.txt '
                f'--fast '
                f'--threads {threads}')

        os.remove('temp-input.txt')
        os.remove('temp-output.txt')

    for input_path in list(outputs_dict):
        segm_path = outputs_dict[input_path]['semantic_segmentation']
        if not os.path.exists(segm_path):
            print('failed segmentation on', input_path)
            del outputs_dict[input_path]

    #######################################################
    # Brain extraction and intensity normalization         #
    #######################################################

    def mask_and_normalize(paths):
        reg_path, seg_path = paths
        output_dir = os.path.dirname(seg_path)
        mask_path  = os.path.join(output_dir, 'mask.nii.gz')
        norm_path  = os.path.join(output_dir, 'normalized.nii.gz')
        brain_path = os.path.join(output_dir, 'brain.nii.gz')

        if os.path.exists(mask_path) and \
           os.path.exists(norm_path) and \
           os.path.exists(brain_path): return

        try:
            reg = nib.load(reg_path)
            seg = nib.load(seg_path)
            reg_arr = reg.get_fdata()
        except:
            print('loading failed for', reg_path)
            return


        if not os.path.exists(mask_path):
            try:
                mask_arr = (seg.get_fdata().round() > 0).astype(np.uint8)
                mask = nib.Nifti1Image(mask_arr, seg.affine, seg.header)
                mask.to_filename(mask_path)
            except:
                print('brain extraction failed for', reg_path)
                return

        if not os.path.exists(norm_path):
            try:
                ws_norm = WhiteStripeNormalize()
                normalized_arr = ws_norm(reg_arr, mask_arr, modality=Modality.T1)
                normalized = nib.Nifti1Image(normalized_arr, reg.affine, reg.header)
                normalized.to_filename(norm_path)
            except:
                print('normalization failed for', reg_path)
                return

        if not os.path.exists(brain_path):
            try:
                brain_arr = normalized_arr.copy()
                brain_arr[ mask_arr == 0. ] = brain_arr.min()
                brain = nib.Nifti1Image(brain_arr, reg.affine, reg.header)
                brain.to_filename(brain_path)
            except:
                print('brain extraction failed for', reg_path)
                return
        
        if os.path.exists(reg_path):
            os.remove(reg_path)


    print('🚀 computing brain mask, intensity normalization and skull stripping')

    reg_seg_pairs = [ (d['affine_registration'], d['semantic_segmentation']) for d in outputs_dict.values() ]

    pool = Pool(processes=threads)
    for _ in tqdm(pool.imap_unordered(mask_and_normalize, reg_seg_pairs), total=len(reg_seg_pairs)):
        pass

    print('🚀 finish.')