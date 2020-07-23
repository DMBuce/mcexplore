#!/usr/bin/python

# mcexplore.py, by similardilemma
# Released under the Creative Commons Attribution-ShareAlike license:
# http://creativecommons.org/licenses/by-sa/3.0/

import os
import sys
import shutil
import optparse
import subprocess
import math
import time

from nbt import nbt

# https://stackoverflow.com/a/11270665
try:
    from subprocess import DEVNULL
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

def main():
    # handle command line options and args
    version = "%prog 1.5"
    usage = "usage: %prog [options] xsize [zsize]"
    description = "Uses a Minecraft server to generate square land of a specified size, measured in chunks (16x16 blocks) or regions (32x32 chunks). xsize and zsize are the extent of the rectangle in the x and z direction, respectively, and must be greater than 25 chunks. If only xsize is specified, it is used for both xsize and zsize. Either run this from the folder containing your minecraft server, or specify the path to your minecraft folder with the -p option."
    parser = optparse.OptionParser(version=version, usage=usage, description=description)
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="When enabled, the Minecraft server output is shown on the console.")
    parser.add_option("-p", "--path", dest="path", default=".", help="Sets the path of the working directory to use when running the server. Defaults to the current directory (.).")
    parser.add_option("-c", "--command", dest="command", default="java -jar minecraft_server.jar nogui", help="Specifies the command used to start the server. Defaults to 'java -jar minecraft_server.jar nogui'.")
    parser.add_option("-x", dest="xorigin", type="int", help="Set the X offset to generate land around. Defaults to the server's spawn point.")
    parser.add_option("-z", dest="zorigin", type="int", help="Set the Z offset to generate land around. Defaults to the server's spawn point.")
    parser.add_option("-r", "--regions", action="store_true", dest="regions", default=False, help="When enabled, measure in regions instead of chunks.")
    (options, args) = parser.parse_args()
    
    # exit with an error if no arguments were passed
    if len(args) == 0:
        print("You must specify a size. Use -h for help.")
        sys.exit(1)

    # if only an xsize was specified, use it for the zsize as well
    if len(args) == 1:
        args.append(args[0])
    
    # exit with an error if a size smaller than the initial spawn was specified
    if options.regions:
        multiplier = 512
        if int(args[0]) < 2 or int(args[1]) < 2:
            print("When specifying sizes in regions, you must specify an area 2x2 or larger.")
            sys.exit(1)
    else:
        multiplier = 16
        if int(args[0]) <= 25 or int(args[1]) <= 25:
            print("Minecraft maps start with a 25x25 chunk square. You must specify sizes larger than this.")
            sys.exit(1)

    # do a dry run if the server hasn't started at least once
    if not os.path.isfile(os.path.join(options.path, 'server.properties')):
        print("Generating world and server.properties")
        runMinecraft(options.path, options.command, options.verbose)

    # parse the server.properties file to get the world name
    properties = parseConfig(os.path.join(options.path, 'server.properties'))
    world = os.path.join(options.path, properties['level-name'])
    
    # make a backup of the level.dat file for later restoration
    level = os.path.join(options.path, world, "level.dat")
    levelbak = os.path.join(options.path, world, "level.dat.explorebackup")
     
    # don't do anything if a backup already exists. Since we always clean up our backups, a leftover backup means something went wrong last time.
    if os.path.isfile(levelbak):
        print("A backup of your level.dat file exists. This means that you've run this program before and it failed, was interrupted, or is still running. You will need to restore or delete this backup before trying again.")
        sys.exit(1)
     
    # make our backup
    shutil.copyfile(level, levelbak)

    # find the server's original spawn point
    originalspawn = getSpawn(level)
    
    # use the spawn point as the origin if none was specified
    if options.xorigin is None: options.xorigin = originalspawn[0]
    if options.zorigin is None: options.zorigin = originalspawn[2]
    
    # move the origin to the nearest valid center point
    # this will be a region or chunk center, the center of a region or chunk border,
    # or the corner of a region or chunk, depending on the specified dimensions
    # this is not strictly necessary when measuring in chunks, but doesn't hurt
    xoffset = (int(args[0]) % 2) * (multiplier / 2)
    zoffset = (int(args[1]) % 2) * (multiplier / 2)
    options.xorigin = int(round(float(options.xorigin + xoffset) / float(multiplier))) * multiplier - xoffset
    options.zorigin = int(round(float(options.zorigin + zoffset) / float(multiplier))) * multiplier - zoffset
    print("Snapped origin to %d, %d" % (options.xorigin, options.zorigin))
    
    # loop through a grid of spawn points within the given range, starting and stopping the server for each one
    # note that the server generated spawn point is 400x400 meters (25x25 chunks), but it does not generate
    # trees or snow outside of a 384x384 meter box.
    spawnsize = 384.0
    xsize = int(args[0]) * multiplier - spawnsize - 16
    zsize = int(args[1]) * multiplier - spawnsize - 16
    print("Size of area to map in meters: %d, %d" % (xsize + spawnsize, zsize + spawnsize))
    xiterations = int(math.ceil(xsize / spawnsize) + 1)
    ziterations = int(math.ceil(zsize / spawnsize) + 1)
    for xcount in range(0, xiterations):
        x = options.xorigin - xsize / 2 + xcount * spawnsize
        if x > options.xorigin + xsize / 2: x = options.xorigin + xsize / 2
        for zcount in range(0, ziterations):
            z = options.zorigin - zsize / 2 + zcount * spawnsize
            if z > options.zorigin + zsize / 2: z = options.zorigin + zsize / 2
            print("Setting spawn to %d, %d" % (x, z))
            setSpawn(level, (int(x), 64, int(z)))
            runMinecraft(options.path, options.command, options.verbose)

    # restore the old spawn point
    print("Restoring original spawn of %d, %d, %d" % originalspawn)
    os.remove(level)
    os.rename(levelbak, level)

def getSpawn(level):
    """Gets the spawn point from a given level.dat file"""
    data = nbt.NBTFile(level,'rb')["Data"]
    return (data['SpawnX'].value, data['SpawnY'].value, data['SpawnZ'].value)

def setSpawn(level, coords):
    """Sets the spawn point in a given level.dat file"""
    f = nbt.NBTFile(level,'rb')
    (f["Data"]["SpawnX"].value, f["Data"]["SpawnY"].value, f["Data"]["SpawnZ"].value) = coords
    f.write_file(level)

def runMinecraft(path, command, verbose=False):
    """Runs a minecraft server, and stops it as soon as possible."""
    if verbose:
        outstream = sys.stdout
    else:
        outstream = DEVNULL
    mc = subprocess.Popen(command.split(), cwd=path, stdin=subprocess.PIPE, stdout=outstream, universal_newlines=True)
    mc.communicate("/stop\n")
    mc.wait()

def parseConfig(filename):
    """Parses a server.properties file. Accepts the path to the file as an argument, and returns the key/value pairs."""
    properties = {}
    f = open(filename, 'r')
    for line in f:
        line = line.strip()
        if not line.startswith("#"):
            (key, sep, val) = line.partition("=")
            properties[key] = val
    return properties

if __name__ == "__main__":
    main()
