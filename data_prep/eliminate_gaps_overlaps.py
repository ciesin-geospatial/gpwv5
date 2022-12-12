import arcpy
import argparse
import sys

arcpy.env.addOutputsToMap = True

def check_fc(in_fc):
    ''' checks that input feature class is '''
    gaps = True
    overlaps = True
    flds = [fld.name for fld in arcpy.ListFields(in_fc)]
    if 'AREA_SQKM' not in flds:
        arcpy.AddError(f'Field AREA_SQKM is required and cannot be found in {in_fc}')
    if 'gaps' not in flds:
        gaps = False
    if 'overlaps' not in flds:
        overlaps = False
    
    if not any((gaps, overlaps)):
        arcpy.AddError(f"No overlap or gap field found in {in_fc}")
        sys.exit(1)

    return(gaps, overlaps)

    
def run_eliminate(fc, where):
    ''' eliminate gaps and overlaps smaller than the maximum area'''
    new_fc = None

    # make a feature layer with the selection
    lyr = arcpy.MakeFeatureLayer_management(fc, 'lyr')
    # check the count to make sure something is selected
    arcpy.SelectLayerByAttribute_management(lyr, 'NEW_SELECTION', where)

    # run the eliminate and return the result
    out_fc = fc + '_elim'
    arcpy.management.Eliminate(
        lyr,
        out_fc
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
    description='Eliminate gaps and overlaps.')
    parser.add_argument('input_features',
        help='Path and file name of input feature class (output of Check input Boundaries script/tool).')
    parser.add_argument('max_area',
        help='Maximum area (square kilometers) of gap/overlap to automatically remove.')


    args = parser.parse_args()
    arcpy.AddMessage('checking inputs...')
    g, o = check_fc(args.input_features)

    if all((g,o)):
        query = f'(gaps = 1 OR overlaps = 1) AND AREA_SQKM < {args.max_area}'
    elif g:
        query = f'gaps = 1 AND AREA_SQKM < {args.max_area}'
    elif o:
        query = f"overlaps = 1 AND AREA_SQKM < {args.max_area}"
    arcpy.AddMessage(f'Where query: {query}')
    arcpy.AddMessage(f'Eliminating polygons from {args.input_features}')
    run_eliminate(args.input_features, query)


