import arcpy
import argparse
import os
import sys

# template project
# TODO: move to network path and reference there
template = r"F:\GPWv5_prototyping\projects\gaps_overlapps_template\gaps_overlapps_template.aprx"
layers_to_update = {"overlaps", "gaps", "admin_union"}
original_layer = 'original_loaded'

def setup_project(fc):
    '''Import layers from template feature class and update source to the input feature class. '''
    aprx = arcpy.mp.ArcGISProject('current')
    to_path = fc[:fc.rfind('\\')]
    to_fc = fc[fc.rfind('\\')+1:]
    if any(isinstance(x, int) for x in (to_fc, to_path)):
        arcpy.AddWarning(f'Cannot find {fc}')
        arcpy.AddError('Please specify full input path to feature class.')
        sys.exit(1)

    if '.gdb' not in to_path:
        arcpy.AddMessage(f'Error, expected input to be in a File Geodatabase.')
        sys.exit(1)
    iso = to_fc[:3]
    orig_fc = f'{iso}_ingest'

    # create the dict of new layer connection properties
    replace_dict = {'connection_info': {'database': f'{to_path}'}, 
                'dataset': f'{to_fc}', 
                'workspace_factory': 'File Geodatabase'}
    # import the map
    aprx.importDocument(template)
    # update the data source
    m = aprx.listMaps('Gaps*')[0]
    m.name = 'Gaps and Overlaps'

    for lyr in m.listLayers():
        if lyr.name in layers_to_update:
            arcpy.AddMessage(f'Updating {lyr.name}')
            # arcpy.AddMessage(f'{lyr.connectionProperties}')
            lyr.updateConnectionProperties(
                lyr.connectionProperties, 
                replace_dict        
            )
        elif lyr.name == original_layer:
            ## update the original ingest layer if it exists
            if arcpy.Exists(f'{to_path}/{orig_fc}'):
                update_dict = {
                    'connection_info': {'database': f'{to_path}'}, 
                    'dataset': f'{orig_fc}', 
                    'workspace_factory': 'File Geodatabase'
                }
                lyr.updateConnectionProperties(
                lyr.connectionProperties, 
                replace_dict        
            )
            else:
                ## remove the layer if it doesn't exist
                m.removeLayer(lyr)
    aprx.save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Set up boundary files for review.')
    parser.add_argument('input_features',
        help='Path and file name of input feature class (output of Check input Boundaries script/tool).')

    args = parser.parse_args()
    if not arcpy.Exists(args.input_features):
        arcpy.AddError(f'Cannot find input feature class {args.input_features}')
        sys.exit(1)

    setup_project(args.input_features)