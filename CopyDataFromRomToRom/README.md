## Copy Data from Rom to Rom

This tool will help you copy data from one Rom to another, based on the EcuFlash definitions for those Roms.

It usually comes in handy if you compile a new version of your MerpMod patch and want to apply it to your Rom. You usually had to copy the tables from the old Rom to the new one, or remove the patch from the old Rom and apply the new patch, and then copy patch related tables.

### Specs

The tool will copy only those tables that match between Roms. For 2 tables to match, they have to have the same name, same columns, same sizes for columns / data, same scaling and same address.

For the address verification, there's an option to disable it if you want to.

The script loads the definitions for each Rom from the folders you provide. Then, it ignores tables that don't have all the specs (scaling, address, sizes). This means that it will ignore all tables from the base definition that do not have an equivalent in your Rom.

### Use

Example for copying data between two `AZ1G202G` Roms.
Folder structure:
```
-> Defs_old
---- 32BITBASE.xml
---- AZ1G201G.xml
---- AZ1G202G.xml
---- AZ1G202G.MeRpMoD.Switch.Testing.v00.60.d16.4.30.1000.xml
-> Defs_new
---- 32BITBASE.xml
---- AZ1G201G.xml
---- AZ1G202G.xml
---- AZ1G202G.MeRpMoD.Switch.Testing.v00.60.d17.4.31.1000.xml
-> copyDataFromRomToRom.py
-> AZ1G202G_patched_old.bin
-> AZ1G202G_patched_new.bin
```

`32BITBASE.xml`, `AZ1G201G.xml` and `AZ1G202G.xml` are common files between the two Roms.

`AZ1G202G.xml` has an include tag for `AZ1G201G.xml`, and the latter has an include tag for `32BITBASE.xml`.

##### Normal Use: 
`copyDataFromRomToRom.py AZ1G202G_patched_old.bin AZ1G202G_patched_new.bin defs_old defs_new`
##### Output processed definitions: 
`copyDataFromRomToRom.py --outputdefs AZ1G202G_patched_old.bin AZ1G202G_patched_new.bin defs_old defs_new`
##### Ignore address match
`copyDataFromRomToRom.py --outputdefs --nomatch AZ1G202G_patched_old.bin AZ1G202G_patched_new.bin defs_old defs_new`
##### Debug
`copyDataFromRomToRom.py --debug --outputdefs AZ1G202G_patched_old.bin AZ1G202G_patched_new.bin defs_old defs_new`

Debug mode will take all output and write it with the append option to "output.txt" file.

## Disclaimer

Please use with caution and at your own risk. I'm not responsable for any damage you may cause while using this script.
I've tested it out pretty extensively, but bugs might still occur.
Please double check the scripts results in EcuFlash for each combination of Rom and definitions. There are sometimes inconsistancies in the definitions that may cause problems.

Also, please use the "--debug" switch and check the output. 