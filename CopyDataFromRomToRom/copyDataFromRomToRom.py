"""
Name: copyDataFromRomToRom
Version: 0.2
Author: CIA

Changelog:
V 0.2
    - Added table_blacklist - with ECU Identifier - so i don't brick my ECU again.
"""
import sys
import os
import xml.etree.ElementTree as ET
import logging
import argparse
import pprint
import traceback


"""
==========================
    Errors
==========================
"""
error_3d_static = "Found 3D table {0} with static column. Unexpected till now."
error_table_type = "Unknown table type {0} - exiting"
error_scaling_memorisez = "Scaling {0} is already memorisez in <scalings>. This should not happen!"
error_invalid_path = "{0} is not a valid path to a file"
error_invalid_scaling = "Found invalid scaling {0} - does not contain field {1}"
error_invalid_common_tables = "No tables to copy - common tables - received None."
error_inpropper_argument = "I've received an inpropper argument type: {0}"
error_invalid_type_of_object = "Invalid type of object received"

debug_found_common_table = "\t\tFound common table: {0}"
debug_getting_common_tables_between = "\tGetting common tables between {0} and {1}"
debug_copying_table = "\tCopying table {0}"
debug_copy_info = "\t\t\tCopying from addr: {0} size: {1} to addr: {2} size: {3}"

info_initial_action = "Copying data from ROM {0} to ROM {0}"
info_step1 = "\tLoading ROMs and Defs..."
info_step1_finish = "\tFinished load."
info_step2 = "\tCopying data..."
info_step3 = "\tDumping to file"

t1D = "1D"
t2D = "2D"
t3D = "3D"

table_blacklist = [
    "ECU Identifier",
    "ecu id"
]


def myerror(errormsg):
    err = "{0}\n\n{1}".format(errormsg, traceback.format_exc())
    raise RuntimeError(err)


def checkNone(field, error, *args):
    if field is None:
        myerror(error.format(*args))


def check(expr, error, *args):
    if not expr:
        myerror(error.format(*args))
            

def getDictNthKey(adic, n):
    try:
        return list(adic)[n]
    except IndexError:
        return None

"""
==========================
    RomHandler 
==========================
"""

class RomHelpers(object):
    """Container for generic helpers."""

    @staticmethod
    def getSizeOfScaling(storagetype):
        """Retrieves size of datatype."""
        if storagetype == "float":
            return 4
        if storagetype == "bloblist":
            return 4
        if storagetype == "uint8":
            return 1
        if storagetype == "uint16":
            return 2


class RomsOps(object):
    """Handler class for various ROM to ROM operations."""

    """ =========== Statics. ============ """

    @staticmethod
    def checkTableMatch(one, other, tname, address_match=True):
        """Check if the table completely matches."""
        def __tableCheckEQ(o1, o2, path):
            t1 = o1.tables
            t2 = o2.tables
            for x in path:
                t1 = t1.get(x, None)
                t2 = t2.get(x, None)

                if t1 is None and t2 is None:
                    return True
                if t1 is None or t2 is None:
                    return False

            if t1 == t2:
                return True
            return False


        if tname not in other.tables:
            return False
        if tname not in one.tables:
            return False
        if not __tableCheckEQ(one, other, [tname, "elements"]):
            return False
        if not __tableCheckEQ(one, other, [tname, "itemsize"]):
            return False
        if not __tableCheckEQ(one, other, [tname, "scaling"]):
            return False
        if not __tableCheckEQ(one, other, [tname, "type"]):
            return False
        if not __tableCheckEQ(one, other, [tname, "subt", "X", "elements"]):
            return False
        if not __tableCheckEQ(one, other, [tname, "subt", "X", "itemsize"]):
            return False
        if not __tableCheckEQ(one, other, [tname, "subt", "X", "scaling"]):
            return False
        if not __tableCheckEQ(one, other, [tname, "subt", "X", "static"]):
            return False
        if not __tableCheckEQ(one, other, [tname, "subt", "Y", "elements"]):
            return False
        if not __tableCheckEQ(one, other, [tname, "subt", "Y", "itemsize"]):
            return False
        if not __tableCheckEQ(one, other, [tname, "subt", "Y", "scaling"]):
            return False
        if not __tableCheckEQ(one, other, [tname, "subt", "Y", "static"]):
            return False

        if address_match:
            if not __tableCheckEQ(one, other, [tname, "address"]):
                return False
            if not __tableCheckEQ(one, other, [tname, "subt", "X", "address"]):
                return False
            if not __tableCheckEQ(one, other, [tname, "subt", "Y", "address"]):
                return False
        return True

    @staticmethod
    def getCommonTablesWith(one, other, address_match=True):
        """Retrieve common tables with another ROM."""
        if type(other) != RomHandler:
            myerror(error_invalid_type_of_object)
        if type(one) != RomHandler:
            myerror(error_invalid_type_of_object)

        common = []
        for tname in one.tables:
            if RomsOps.checkTableMatch(one, other, tname, address_match):
                common.append(tname)

        return common

    @staticmethod
    def getCommonTables(roms, address_match=True):
        """Retrieve common tables between the Roms."""
        if type(roms) != type([]):
            myerror(error_inpropper_argument.format(type(roms)))
        if len(roms) < 2:
            return []

        common = roms[0] % roms[1]
        common_set = set(common)
        for rom in roms[2:]:
            new_common = rom[0] % rom[2]
            new_common_set = set(new_common)

            common_set = common_set.intersection(new_common_set)

        return list(common_set)

    @staticmethod
    def getOffsetsPairsForTable(source, dest, tname):
        """Retrieve all offsets and sizes for a table, in pairs."""
        def _buildSet(offsets, ts, td):
            setx = (
                int(ts["address"], 16),
                int(ts["elements"]) * int(ts["itemsize"]),
                int(td["address"], 16),
                int(td["elements"]) * int(td["itemsize"])
                )
            offsets.append(setx)

        offsets = []

        ts = source.tables[tname]
        td = dest.tables[tname]
        _buildSet(offsets, ts, td)

        if source.tables[tname]["type"] != t1D:
            ts = source.tables[tname]["subt"]
            ts = ts[getDictNthKey(ts, 0)]
            td = dest.tables[tname]["subt"]
            td = td[getDictNthKey(td, 0)]

            if 'static' not in ts:
                _buildSet(offsets, ts, td)

        if source.tables[tname]["type"] == t3D:
            ts = source.tables[tname]["subt"]
            ts = ts[getDictNthKey(ts, 1)]
            td = dest.tables[tname]["subt"]
            td = td[getDictNthKey(td, 1)]
            _buildSet(offsets, ts, td)

        return offsets               

    @staticmethod
    def copyRomData(source, dest, address_match):
        """Copy rOM data from source to destionation."""
        common_tables = RomsOps.getCommonTablesWith(source, dest, address_match)

        for tname in common_tables:
            logging.debug(debug_copying_table.format(tname))

            offsets = RomsOps.getOffsetsPairsForTable(source, dest, tname)

            for items in offsets:
                logging.debug(debug_copy_info.format(
                    hex(items[0]),
                    items[1],
                    hex(items[2]),
                    items[3]))
                data = source.getData(items[0], items[1])
                dest.setData(items[2], items[3], data)


class RomHandler(object):
    """Generic container for handleling a ROM file, including definitions."""

    def __init__(self, rom_path, defs_path):
        self.rom_path = rom_path
        self.defs_path = defs_path

        self.defs = []
        self.tables = {}
        self.scalings = {}

    def __str__(self):
        return pprint.pformat(self.tables, indent=4)

    def __mod__(self, other):
        return RomsOps.getCommonTablesWith(self, other)

    """ =========== Helpers. ============ """

    def _addToTable(self, name, xml, key):
        """Helper to add resources to tables."""
        if name not in self.tables:
            self.tables[name] = {}

        it = xml.get(key, None)
        if it is not None:
            self.tables[name][key] = it

    def _addToTargetTable(self, target, name, xml, key):
        """Helper to add resources to tables."""
        if name not in target:
            target[name] = {}

        it = xml.get(key, None)
        if it is not None:
            target[name][key] = it

    """ =========== Private. ============ """

    def _loadDefs(self):
        """Load definitions as XML tree objects."""
        for fl in os.listdir(self.defs_path):
            if fl.endswith(".xml"):
                flpath = os.path.join(self.defs_path, fl)

                root = ET.parse(flpath).getroot()
                self.defs.append((fl, root))

    def _loadScalings(self):
        """Load table scalings."""
        for xml in self.defs:
            xml = xml[1]
            for scalingtag in xml.findall("scaling"):
                name = scalingtag.get("name", None)
                storagetype = scalingtag.get("storagetype", None)

                checkNone(name, error_invalid_scaling, str(scalingtag), "name")
                checkNone(storagetype, error_invalid_scaling, name, "storagetype")
                #check(name not in self.scalings, error_scaling_memorisez, name)

                itemsize = RomHelpers.getSizeOfScaling(storagetype)
                self.scalings[name] = {"type":storagetype, "itemsize":itemsize}

    def _processScaling(self, target):
        if "scaling" in target:
            if target["scaling"] in self.scalings:
                target["itemsize"] = self.scalings[target["scaling"]]["itemsize"]
            else:
                target["itemsize"] = 4

    def _process2D(self, ttag, name, subtables):
        """Process 2D subtable."""
        subt_xml = subtables[0]
        ttype = subt_xml.get("type", "").lower()
        
        self._addToTargetTable(self.tables[name]["subt"], "Y", subt_xml, "elements")
        self._addToTargetTable(self.tables[name]["subt"], "Y", subt_xml, "address")
        self._addToTargetTable(self.tables[name]["subt"], "Y", subt_xml, "scaling")

        target = self.tables[name]["subt"]["Y"]
        self._processScaling(target)

        if "static" in ttype:
            target["static"] = True
            self.tables[name]["static"] = True

        y_size = int(subt_xml.get("elements", "1"), 10)
        return 1, y_size

    def _process3D(self, ttag, name, subtables):
        """Process 3D subtable."""
        subt_1_xml = subtables[0]
        subt_2_xml = subtables[1]

        ttype = subt_1_xml.get("type", "").lower()
        check("static" not in ttype, error_3d_static, name)
        ttype = subt_2_xml.get("type", "").lower()
        check("static" not in ttype, error_3d_static, name)

        # X
        self._addToTargetTable(self.tables[name]["subt"], "X", subt_1_xml, "elements")
        self._addToTargetTable(self.tables[name]["subt"], "X", subt_1_xml, "address")
        self._addToTargetTable(self.tables[name]["subt"], "X", subt_1_xml, "scaling")

        targetX = self.tables[name]["subt"]["X"]
        self._processScaling(targetX)
        x_size = int(targetX.get("elements", "1"), 10)

        # Y
        self._addToTargetTable(self.tables[name]["subt"], "Y", subt_2_xml, "elements")
        self._addToTargetTable(self.tables[name]["subt"], "Y", subt_2_xml, "address")
        self._addToTargetTable(self.tables[name]["subt"], "Y", subt_2_xml, "scaling")

        targetY = self.tables[name]["subt"]["Y"]
        self._processScaling(targetY)
        y_size = int(targetY.get("elements", "1"), 10)

        # Correction on possible missing data
        corrected = False
        if "elements" in targetX and "elements" not in targetY:
            targetY["elements"] = targetX["elements"]
            y_size = int(targetY["elements"], 10)
            corrected = True
        if "elements" in targetY and "elements" not in targetX:
            targetX["elements"] = targetY["elements"]
            x_size = int(targetX["elements"], 10)
            corrected = True

        if corrected:
            logging.debug("Correcting table {0}".format(name))

        return x_size, y_size

    def _processSubtables(self, ttag, name):
        """Extract subtable data."""
        x_size = 1
        y_size = 1
        
        # Setup
        if "subt" not in self.tables[name]:
            self.tables[name]["subt"] = {}
        subtables = ttag.findall("table")

        # Processing the table
        target = self.tables[name]["type"]
        if target == t1D:
            pass
        elif target == t2D:
            if len(subtables):
                x_size, y_size = self._process2D(ttag, name, subtables)
        elif target == t3D:
            if len(subtables):
                x_size, y_size = self._process3D(ttag, name, subtables)
        else:
            error = error_table_type.format(self.tables[name]["type"])
            myerror(error)

        # Small correction for certain types of data
        update = False
        if "elements" in self.tables[name]:
            if "static" not in self.tables[name]:
                update = True
        else:
            update = True

        if update:
            self.tables[name]["elements"] = x_size * y_size

    def _cleanupTables(self):
        """Remove unvalid tables for this ROM."""
        to_delete = []
        for tname in self.tables:
            delete = False
            if "address" not in self.tables[tname]:
                delete = True
            if "elements" not in self.tables[tname]:
                delete = True
            if "type" not in self.tables[tname]:
                delete = True

            if "subt" in self.tables[tname]:
                target = self.tables[tname]["subt"]
                for item in target:
                    if "static" not in target[item]:
                        if "address" not in target[item]:
                            delete = True
                        if "elements" not in target[item]:
                            delete = True

            if delete:
                to_delete.append(tname)

        for tname in self.tables:
            for black in table_blacklist:
                if black.lower() in tname.lower():
                    to_delete.append(tname)

        logging.debug("Cleaning up tables for {0}".format(self.rom_path))
        for item in to_delete:
            logging.debug("\tRemoving table {0}".format(item))
            self.tables.pop(item, None)

    def _correctTables(self):
        """Do correction operations on tables that do not respect common format.""" 
        for tname in self.tables:
            if self.tables[tname]["type"] == t3D:
                size1 = self.tables[tname]["subt"]["X"]["elements"]
                size2 = self.tables[tname]["subt"]["Y"]["elements"]
                self.tables[tname]["elements"] = int(size1) * int(size2)

        for tname in self.tables:
            if self.tables[tname]["type"] == t2D:
                key = getDictNthKey(self.tables[tname]["subt"], 0)
                sz = self.tables[tname]["subt"][key]["elements"]
                self.tables[tname]["elements"] = int(sz)

    def _processTableFromDef(self, defroot):
        """Process a definition to load into memory."""
        for ttag in defroot.findall("table"):
            name = ttag.get("name")

            if "Feedback Correction" in name:
                i = 1

            self._addToTable(name, ttag, "type")
            self._addToTable(name, ttag, "scaling")
            self._addToTable(name, ttag, "address")
            
            target = self.tables[name]
            self._processScaling(target)

            if "type" in target:
                self._processSubtables(ttag, name)

    def _loadTables(self):
        """Load tables into memory."""

        for xml in self.defs:
            if "bitbase" in xml[0].lower():
                self._processTableFromDef(xml[1])

        for xml in self.defs:
            if "bitbase" not in xml[0].lower():
                self._processTableFromDef(xml[1])            

        self._cleanupTables()
        self._correctTables()

    """ =========== Public. ============= """

    def load(self):
        """Load data (rom & defs) into memory."""
        with open(self.rom_path, "rb") as fp:
            self.content = bytearray(fp.read())

        self._loadDefs()
        self._loadScalings()
        self._loadTables()

    def getData(self, offset, size):
        """Retrieve binary data."""
        return self.content[offset:(offset+size)]

    def setData(self, offset, size, data):
        """Set binary data."""
        self.content[offset:(offset+size)] = data

    def dumpToFile(self):
        """Dump ROM to file."""
        with open(self.rom_path, "wb") as fp:
            fp.write(self.content)


"""
==========================
    Main Logic
==========================
"""

def main(args):
    """Main."""
    logging.info(info_initial_action.format(args.rom1, args.rom2))

    # Load data
    logging.info(info_step1)

    source_rom = RomHandler(args.rom1, args.def1)
    dest_rom = RomHandler(args.rom2, args.def2)
    source_rom.load()
    dest_rom.load()

    if args.outputdefs:
        with open(args.rom1+".defs", "w") as fp:
            fp.write(str(source_rom))
        with open(args.rom2+".defs", "w") as fp:
            fp.write(str(dest_rom))

    logging.info(info_step1_finish)
    logging.info(info_step2)

    RomsOps.copyRomData(source_rom, dest_rom, args.address_match)

    logging.info(info_step3)

    source_rom.dumpToFile()
    dest_rom.dumpToFile()


def parseArgs():
    """Parsing arguments."""
    epilog = """
    In this version, the definitions for each ROM must be manually selected.
    You take your ROM definition (az1g202g.xml for example) and follow the include trail
    (look inside the XML for the <include> tag) till you copy all the files (you reach 32bitbase.xml)
    """
    parser = argparse.ArgumentParser(description='Copy one ROM settings to another.', epilog=epilog)
    parser.add_argument('rom1', help='Source ROM from which to copy (OLD ONE)')
    parser.add_argument('rom2', help='Destination ROM to which to copy (NEW ONE)')
    parser.add_argument('def1', help='Definitions for the first ROM, all in one folder (just them)')
    parser.add_argument('def2', help='Definitions for the second ROM, all in a second folder (just them)')
    parser.add_argument('--nomatch', '-n', dest='address_match', action='store_const',
                        const=False, default=True,
                        help='The addresses of the tables must not perfectly match (default to TRUE)')
    parser.add_argument('--debug', '-d', dest='debug_mode', action='store_const',
                        const=True, default=False,
                        help='Activate debug mode.')
    parser.add_argument('--outputdefs', '-o', dest='outputdefs', action='store_const',
                        const=True, default=False,
                        help='Output table tree of defs to files on disk.')

    args = parser.parse_args()
    return args


def validateInput(args):
    """Validate the input."""
    if not os.path.exists(args.rom1):
        myerror(error_invalid_path.format("Rom1"))
    if not os.path.exists(args.rom2):
        myerror(error_invalid_path.format("Rom2"))
    if not os.path.exists(args.def1):
        myerror(error_invalid_path.format("Def1"))
    if not os.path.exists(args.def2):
        myerror(error_invalid_path.format("Def2"))


def setup(args):
    """Generic setup based on options."""
    if args.debug_mode:
        logging.basicConfig(filename='output.log', level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    args = parseArgs()
    validateInput(args)
    setup(args)
    
    main(args)
