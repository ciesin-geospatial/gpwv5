# check_input_boundaries.py
# validate input feature class for several 
# checks:
# 1. geometry errors
# 2. projection information
# 3. reserved field names
# 4. iso code
# 5. gaps
# 6. overlaps

# G. Yetman August 2022
##################
'''   Imports  '''
##################
import argparse
import arcpy
import sys

from collections import defaultdict
from numpy import average
from pathlib import Path

###################
''' Global Vars '''
###################
arcpy.overwriteOutput = True

# unsupported iso codes
# TODO: check that this list is complete
# and what we use for Andorra! Also, 
# don't we need to change IN? 
ISOS_TO_CHANGE = {
    'and': 'adr',
    'vat': 'vcs'
}
BAD_ISOS = set(ISOS_TO_CHANGE.keys())
RESERVED_WORDS_FILE = r"\\dataserver1\GPW\GPW5\Scripts\Ingest\reference_data\reserved_words.txt"

###################
'''  Functions  '''
###################

def _read_reserved_words():
    ''' reads in reserved words (unsupported field names) from the network'''
    reserved_words = set()
    arcpy.AddMessage('Reading in reserved keywords.')
    try:
        with open(RESERVED_WORDS_FILE, 'r') as f:
            for line in f:
                reserved_words.add(line.strip())
    except IOError:
        arcpy.AddWarning('Unable to read list of reserved keywords, field names cannot be checked!')
        arcpy.AddMessage('Tried to read words from file: ')
        arcpy.AddMessage(f'{RESERVED_WORDS_FILE}')
    return reserved_words


def _check_input_params(fc,ows, iso):
    '''check input parameters: feature class, iso, output folder. '''
    if not arcpy.Exists(fc):
        arcpy.AddError(f'Input feature class {fc} not found!')
        arcpy.AddError('Please check your inputs and try again.')
        sys.exit(1)
    arcpy.AddMessage('Creating output path.')
    Path(ows).mkdir(parents=True, exist_ok=True)

    arcpy.AddMessage("Creating output Geodatabase (if it doesn't exist).")
    out_gdb = f'{iso}_ingest.gdb'
    # convert workspace to full path (if it's a relative path, causes a bug later on)
    ows = Path(ows).absolute().as_posix()
    if not arcpy.Exists(rf'{ows}\{out_gdb}'):
        arcpy.management.CreateFileGDB(ows, out_gdb)
    return(rf'{ows}\{out_gdb}')


def check_iso_code(iso):
    ''' check that ISO should not be changed'''
    iso = iso.lower()
    if iso in BAD_ISOS:
        iso = ISOS_TO_CHANGE.get(iso)

    return iso
    
def check_fields(fc): 
    ''' check if any of the fields have a reserved name or invalid starting character'''
    changed_names = {}
    reserved_words = _read_reserved_words()
    flds = [fld.name.upper() for fld in arcpy.ListFields(fc)]
    arcpy.AddMessage(f'Checking feature class field names: \n{flds}')
    for fld in flds:
        if fld in reserved_words:
            changed_names[fld] = fld + '_'
            arcpy.AddMessage(f'Field {fld} is a reserved name, adding an underscore.')
    # Rare, but this has happened when OS or custom libraries are used to 
    # write a shapefile from another format and they don't validate field names
    arcpy.AddMessage('Checking for edge cases: digit or underscore starting a field.')
    for fld in flds:
        if fld[:1].isdigit():
            changed_names[fld] = 't_' + fld
        elif fld[:1] == '_':
            changed_names[fld] =  't' + fld
    return changed_names


def check_geometry(fc):
    ''' check that the feature class has valid geometry. Also check the feature type and
    if a spatial reference is defined.'''
    repair_geometry = None
    topology_tests = None
    projection_defined = None
    # get feature class description
    desc = arcpy.da.Describe(fc)    

    arcpy.AddMessage('Checking spatial reference...')
    if desc['spatialReference'].name == 'Unknown':
        projection_defined = False
        arcpy.AddWarning('Spatial reference is NOT defined!')
        arcpy.AddMessage(f"Spatial extent is: {desc['extent']}")
        return repair_geometry, topology_tests, projection_defined
    else:
        projection_defined = True
        arcpy.AddMessage(desc['spatialReference'].name)

    arcpy.AddMessage('Checking geometry...')
    checks = arcpy.CheckGeometry_management(fc,'memory\\check_geom')
    cnt = int(arcpy.GetCount_management(checks)[0])
    arcpy.AddMessage(f'{cnt} geometry errors identified.')
    if cnt > 0: 
        repair_geometry = True
    # clean up in memory table
    arcpy.Delete_management(checks)
    arcpy.AddMessage('Checking geometry type...')

    shape_type = desc['shapeType']
    if shape_type not in  ['Polygon','MultiPatch']:
        
        arcpy.AddWarning(f'Input feature class has {shape_type} geometry, not Polygon!')
        if shape_type == 'MultiPatch':
            topology_tests = True
        else:
            topology_tests = False
    else:
        topology_tests = True

    return repair_geometry, topology_tests, projection_defined

def run_repair(fc, ows):
    ''' repairs the feature class that has errors identified and returns
        an in memory copy'''
        # first, make a copy of the feature class
    arcpy.AddMessage('Making a copy of the feature class.')
        

def make_copy(fc, out_ws, iso, out_sr = None, field_mapping = None):
    ''' make a copy of the feature class, optionally renaming any fields with 
    reserved field names. '''
    arcpy.env.overwriteOutput = True

    if out_sr:
        arcpy.AddWarning('Output coordinate system is different than input')
        arcpy.AddWarning('Check alignment of output features against known reference source.')
        arcpy.env.outputCoordinateSystem = out_sr

    out_fc = f'{iso}_ingest'
    arcpy.AddMessage('Creating working copy of feature class.')
    arcpy.management.CopyFeatures(fc, rf'{out_ws}\{out_fc}')

    if field_mapping:
        arcpy.AddMessage('Renaming fields.')
        arcpy.env.workspace = out_ws
        for key, value in field_mapping.items():
            arcpy.management.AlterField(
                out_fc,
                key,
                value,
            )

    return rf'{out_ws}\{out_fc}'

def overlap_gap_analysis(fc):
    '''Run union and calculate the number of overlaps and gaps in the features'''
    arcpy.AddMessage('Creating and populating unique ID field')
    arcpy.management.AddField(fc, 'union_uid', 'LONG')
    with arcpy.da.UpdateCursor(fc, 'union_uid') as rows:
        for i, row in enumerate(rows):
            row[0] = i+1
            rows.updateRow(row)
    original_count = int(arcpy.management.GetCount(fc)[0])
    arcpy.AddMessage('Running Union operation.')
    fc_union = arcpy.analysis.Union(
        in_features = fc,
        out_feature_class = fc + '_union',
        gaps = 'NO_GAPS',
    )
    arcpy.AddMessage(f'created {fc_union}')
    post_union_count = int(arcpy.management.GetCount(fc_union)[0])
    if post_union_count > original_count:
        arcpy.AddMessage(f'{post_union_count - original_count} overlaps and/or gaps in input feature class')
    else:
        arcpy.AddMessage('No overlaps or gaps found!')
        return fc_union, 0, 0
    arcpy.AddMessage('Counting overlaps and gaps.')
    gaps = 0
    uids = []
    for row in arcpy.da.SearchCursor(fc_union, 'union_uid'):
        if not row[0]:
            gaps += 1
        else:
            uids.append(int(row[0]))
    overlaps = len(uids) - original_count
    arcpy.AddMessage(f'Found {gaps} gaps and {overlaps} overlaps.')
    if any((overlaps, gaps)):
        # get a list of the field names to check
        # when adding new fields for gaps/overlaps
        flds = [fld.name.lower() for fld in arcpy.ListFields(fc_union)]
        # update the area field
        arcpy.management.CalculateGeometryAttributes(
            in_features = fc_union,
            geometry_property = [['AREA_SQKM','AREA_GEODESIC']],
            area_unit = 'SQUARE_KILOMETERS'
        )

    if overlaps > 0:
        arcpy.AddMessage('Flagging overlaps in union of the boundaries.')
        # get a set of ids that are present more than once (polys split by unions)
        # this should be more efficient than a counter for large feature classes
        visited = set()
        dupes = {x for x in uids if x in visited or visited.add(x)}

        if 'overlaps' not in flds:
            arcpy.management.AddField(fc_union, 'overlaps', 'SHORT')
        # get the areas of the overlaps; largest should be the main poly
        arcpy.AddMessage('Checking overlap sizes...')
        overlap_sizes = dict()
        for x in dupes:
            overlap_sizes[x] = [0,0]
        for row in arcpy.da.SearchCursor(fc_union, ['OBJECTID','union_uid', 'AREA_SQKM']):
            if row[0]: # gaps have no id
                # add areas to dict by overlap id if it's larger; leaving the largest value
                # after everything has been parsed. 
                oid = int(row[0])
                id = int(row[1])
                area = float(row[2])
                if id in dupes: 
                    if area > overlap_sizes[id][0]:
                        overlap_sizes[id] = [area,oid]
            
        # get a set of the oids of the largest overlap polygons
        main_overlap_polys = set([x[1] for x in overlap_sizes.values()])
        if len(main_overlap_polys) != len(dupes):
            arcpy.AddWarning('Not all overlap polygons were matched with a central (main) polygon.')
            arcpy.AddWarning('Overlaps should be manually reviewed.')
        else:
            arcpy.AddMessage('Main (central) overlap polygons identified')
        arcpy.AddMessage('Updating union feature class to flag overlaps (1) and central polys (2).')
        with arcpy.da.UpdateCursor(fc_union, ['OBJECTID', 'union_uid', 'overlaps']) as rows:
            for row in rows:
                oid = int(row[0])
                id = int(row[1])
                # overlaps flagged as 1 or 2
                if id in dupes:
                    if oid in main_overlap_polys:
                        row[2] = 2 # central/main poly
                    else:
                        row[2] = 1 # overlap
                else:
                    row[2] = 0 # no overlap
                rows.updateRow(row)
        
    if gaps > 0:
        arcpy.AddMessage('Flagging gaps in union of the boundaries.')
        if 'gaps' not in flds:
            arcpy.management.AddField(fc_union, 'gaps', 'SHORT')
        with arcpy.da.UpdateCursor(fc_union, ['union_uid', 'gaps']) as rows:
            for row in rows:
                if not row[0]:
                    row[1] = 1 # gap
                else:
                    row[1] = 0 # regular or overlap poly
                rows.updateRow(row)

    return fc_union, gaps, overlaps

def calculate_gap_overlap_stats(polys, check_fields=['gaps','overlaps']):
    '''calculate staistics for gaps and overlaps '''
    areas = defaultdict(list)
    poly_area = 0
    check_fields.append('AREA_SQKM')
    for row in arcpy.da.SearchCursor(polys, check_fields):
        for i, fld in enumerate(check_fields[:-1]):
            if int(row[i]) == 1:
                areas[fld].append(float(row[-1]))
            else:
                poly_area += float(row[-1])
    stats = {}
    stats['average unit area excluding gaps and overlaps'] = average(poly_area)
    for key, value in areas.items():
        stats[f'{key} max area'] = max(value)
        stats[f'{key} mean area'] =  average(value)
    return stats


def check_srs(feat):
    '''check that the data are in geographic coordinates on WGS84 system, 
    and returns booleans representing each respectively. '''
    isGeo = False
    wgs84 = False
    desc = arcpy.da.Describe(feat)
    if desc['spatialReference'].type == 'Geographic':
        isGeo = True
    if desc['spatialReference'].datumCode == 6326:
        wgs84 = True
    elif desc['spatialReference'].spheroidCode == 7030:
        wgs84 = True

    if not all((isGeo, wgs84)):
        arcpy.AddWarning('Coordinate system is not Geographic (WGS84), copied feature class will be projected to match')
    return(isGeo, wgs84)




if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Check input boundary feature class for issues.')
    parser.add_argument('input_features',
        help='Path and file name of input feature class (shapefile or geodatabase feature class).')
    parser.add_argument('iso',
        help='3-letter country iso code (or alternate, like U.S. state code).')
    parser.add_argument('out_folder',
        help='Output folder for results (does not have to exist).')
    parser.add_argument('-c', '--check_iso', action='store_true',
        help='Check that ISO code is valid')
    # parser.add_argument('-v', '--verbose', action='store_true',
    #     help='Log more verbosely.')
 
    args = parser.parse_args()

    # _setup_logging(args.verbose)
    # arcpy.AddMessage('ARGS: {}'.format(args))
    # TODO: check iso code against GPWv5 iso master list (Google Table)
    if args.check_iso:
        arcpy.AddMessage('Checking ISO code...')
        iso = check_iso_code(args.iso)
    else:
        iso = args.iso.lower()

    arcpy.AddMessage('Checking input params...')
    ws = _check_input_params(args.input_features, args.out_folder, iso)



    arcpy.AddMessage('Checking field names...')
    updated_names = check_fields(args.input_features)
    if updated_names:
        arcpy.AddMessage('Found fields with reserved words in their names,')
        arcpy.AddMessage('output feature class will have updated names.')
        arcpy.AddMessage('Fields to be changed and the new names are:')
        arcpy.AddMessage(f'{updated_names}')
        arcpy.AddMessage('Field names will be renamed in a copy of the feature class.')
        

    arcpy.AddMessage('Checking geometry...')
    repair, topo, has_proj = check_geometry(args.input_features)
    if not has_proj:
        arcpy.AddError('Projection information is missing.')
        arcpy.AddError('Please investigate and define a projection for the feature class!')
        arcpy.AddError('Exiting without completing script.')
        sys.exit(1)

    # check that the data are in geographic on WGS84. If not, pass in our target WGS84 spatial reference
    # to the copy features function so that the data are projected during the copy
    sr = None
    if not all((check_srs(args.input_features))):
        sr = arcpy.SpatialReference(4326)
    

    if not topo:
        arcpy.AddError('Input feature class does not contain polygons, please check input!')
        sys.exit(1)

    arcpy.AddMessage('Making a copy of the feature class to edit.')
    if updated_names:
        fc_copy = make_copy(args.input_features, ws, iso, sr, updated_names)
    else:
        fc_copy = make_copy(args.input_features, ws, iso, sr)


    if repair:
        arcpy.AddWarning(f'Repairing geometry for {fc_copy}.')
        arcpy.RepairGeometry_management(fc_copy)

    if topo:
        fc_unioned, gap_count, overlap_count = overlap_gap_analysis(fc_copy)
        if all(x > 0 for x in [gap_count, overlap_count]):
            topo_stats = calculate_gap_overlap_stats(fc_unioned, ['gaps','overlaps'])
        elif gap_count > 0:
            topo_stats = calculate_gap_overlap_stats(fc_unioned, 'gaps')
        elif overlap_count > 0:
            topo_stats = calculate_gap_overlap_stats(fc_unioned, 'overlaps')

        arcpy.AddMessage('Overlap and Gap statistics:')
        for key, value in topo_stats.items():
            arcpy.AddMessage(f'{key}: {value:,.4f} square km')

    else:
        arcpy.AddMessage('No gaps or overlaps found in feature class. ')
