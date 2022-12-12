import arcpy
import argparse

#excludes = {'gap', 'overlap'}

def check_counts(updated, orig):
    ''' Check the counts and fields of the original and input feature classes'''
    flds_orig = [fld.name for fld in arcpy.ListFields(orig)]
    flds_update = [fld.name for fld in arcpy.ListFields(updated)]
    mismatch = set(flds_orig).difference(set(flds_update))
    if 'gap' in mismatch:
        mismatch.remove('gap')
    if 'overlap' in mismatch:
        mismatch.remove('overlap')
    if len(mismatch) > 0:
        arcpy.AddWarning('Missing fields in output feature class: ')
        arcpy.AddWarning(f'{mismatch}')
    else:
        arcpy.AddMessage('Input and output fields match.')


    orig_count = int(arcpy.management.GetCount(orig).getOutput(0))
    elim_count = int(arcpy.management.GetCount(updated).getOutput(0))
    if orig_count == elim_count:
        arcpy.AddMessage(f'Feature counts match, {orig_count} polygons in original, {elim_count} in updated')
    elif orig_count > elim_count:
        arcpy.AddWarning(f'Feature count mismatch! The original feature class has {orig_count - elim_count} more polygons than the updated.')
    elif orig_count < elim_count:
        arcpy.AddWarning(f'Feature count mismatch! The updated feature class has {elim_count - orig_count} more polygons than the original.')

    
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
    description='Check updated feature class (post eliminate / manual clean).')
    parser.add_argument('input_features',
        help='Path and file name of input feature class (output of Eliminate script/tool or manual editing).')
    parser.add_argument('original_features',
        help='Copy of original feature class.')

    args = parser.parse_args()
    check_counts(args.input_features, args.original_features)

    
