#!/usr/bin/python

# mcexplore.py
# originally by similardilemma
# maintained by DMBuce
# Released under the Creative Commons Attribution-ShareAlike license:
# http://creativecommons.org/licenses/by-sa/3.0/

from __future__ import print_function

import os
import sys
import shutil
import argparse
import subprocess
import math
import time
from subprocess import DEVNULL

def msg(message="", file=sys.stdout):
    """Prints an info message"""
    print(message, file=file)

def err(message=""):
    """Prints an error message"""
    msg(message, file=sys.stderr)

# make sure nbt module is installed
try:
    from nbt import nbt
except ImportError:
    err("Couldn't import module: nbt")
    err()
    err("Make sure you followed the install procedure:")
    err("\thttps://github.com/dmbuce/mcexplore#install")
    sys.exit(1)

def getParser():

    # set some vars
    prog = "mcexplore"
    version = f'{prog} 2.122.gf700e33+1'
    description = "Use a minecraft server jar to generate a rectangular section of the world."
    basenames = {
        'levelbak': "level.dat.explorebackup",
        'regionbak': "region.explorerename-overworld",
    }

    # parse args
    parser = argparse.ArgumentParser(prog=prog, description=description, add_help=False)
    opthelp = {
        'xsize': 'The size to generate in the x direction. Measured in chunks (16x16 blocks) by default (but see the -r option, below). Must be greater than 25 chunks.',
        'zsize': "The size to generate in the z direction. Measured in chunks (16x16 blocks) by default (but see the -r option, below). Must be greater than 25 chunks. Defaults to the value provided for 'xsize'.",
        'V': "Show version number and exit.",
        'h': "Show this help message and exit.",
        'c': "The command used to start the server. Defaults to 'java -jar minecraft_server.jar nogui'.",
        'd': "The ID and region folder of the dimension to generate. Relative folder paths are interpreted relative to '--path'. Defaults to 'minecraft:overworld=world/region'.",
        'p': "The working directory to use when running the server. Defaults to the current directory (.).",
        'r': "Use units of regions (32x32 chunks) instead of chunks for 'xsize' and 'zsize'.",
        'x': "The X offset to generate land around. Defaults to the server spawn point.",
        'z': "The Z offset to generate land around. Defaults to the server spawn point.",
        'q': "Suppress minecraft server output. This is the default behavior.",
        'v': "Show minecraft server output.",
    }
    parser.add_argument(
        'xsize', type=int, help=opthelp['xsize']
    )
    parser.add_argument(
        'zsize', type=int, help=opthelp['zsize'],
        nargs='?', default=None
    )
    parser.add_argument(
        "-c", "--command", help=opthelp['c'],
        default="java -jar minecraft_server.jar nogui"
    )
    parser.add_argument(
        "-d", "--dimension", help=opthelp['d'],
        default="minecraft:overworld=world/region"
    )
    parser.add_argument(
        "-p", "--path", help=opthelp['p'],
        default="."
    )
    parser.add_argument(
        "-r", "--regions", help=opthelp['r'],
        default=False, action="store_true"
    )
    parser.add_argument(
        "-x", dest="xorigin", help=opthelp['x'],
        default=None, type=int
    )
    parser.add_argument(
        "-z", dest="zorigin", help=opthelp['z'],
        default=None, type=int
    )
    parser.add_argument(
        "-q", "--quiet", help=opthelp['q'],
        dest="verbose", default=False, action="store_false"
    )
    parser.add_argument(
        "-v", "--verbose", help=opthelp['v'],
        dest="verbose", default=False, action="store_true"
    )
    parser.add_argument(
        "-V", "--version", help=opthelp['V'],
        action="version", version=version
    )
    parser.add_argument(
        "-h", "--help", help=opthelp['h'],
        action="help"
    )

    return parser

def main():
    """Main entry point for the script"""

    # parse args
    parser = getParser()
    prog = parser.prog
    args = parser.parse_args()
    xsize = args.xsize
    zsize = args.zsize if args.zsize else args.xsize

    # validate args
    if "=" not in args.dimension:
        parser.print_usage(file=sys.stderr)
        err("%s: error: argument -d: dimension not specified as 'id=folder': '%s'" % (prog, args.dimension.replace("'", "\\'")))
        sys.exit(1)

    # set some vars
    multiplier = 512 if args.regions else 16
    mcoutput = sys.stdout if args.verbose else DEVNULL
    serverprops = os.path.join(args.path, 'server.properties')
    (dimension, sep, regionfolder) = args.dimension.partition("=")
    if ":" not in dimension:
        dimension = "minecraft:" + dimension

    # make sure sizes are reasonable
    if args.regions and xsize < 2:
        err("xsize too small: %s" % xsize)
        err()
        err("The area to generate must be 2x2 regions or larger.")
        sys.exit(1)
    elif args.regions and zsize < 2:
        err("zsize too small: %s" % zsize)
        err()
        err("The area to generate must be 2x2 regions or larger.")
        sys.exit(1)
    elif xsize <= 25:
        err("xsize too small: %s" % xsize)
        err()
        err("The area to generate must be 26x26 chunks or larger.")
        sys.exit(1)
    elif zsize <= 25:
        err("zsize too small: %s" % zsize)
        err()
        err("The area to generate must be 26x26 chunks or larger.")
        sys.exit(1)

    # check if backup of level.dat or renamed region folder already exist
    for dirpath, dirnames, filenames in os.walk(args.path):
        if basenames['levelbak'] in filenames:
            err("Backup of %s already exists: %s" % ("level.dat", os.path.join(dirpath, basenames['levelbak'])))
            err()
            err("Either %s failed, was interrupted, or is still running." % prog)
            sys.exit(1)
        elif basenames['regionbak'] in dirnames:
            err("Renamed overworld folder already exists: %s" % os.path.join(dirpath, basenames['regionbak']))
            err()
            err("Either %s failed, was interrupted, or is still running." % prog)
            sys.exit(1)

    # start and stop server if server.properties doesn't exist
    if not os.path.isfile(serverprops):
        msg("Generating server files")
        runMinecraft(args.path, args.command, mcoutput)

    # warn the user if the EULA hasn't been accepted
    eula = os.path.join(args.path, "eula.txt")
    if not checkEulaAccepted(eula):
        err("You have not agreed to the Minecraft End User License Agreement: %s" % (eula))
        sys.exit(1)

    # get server properties
    if os.path.isfile(serverprops):
        properties = parseConfig(serverprops)
    else:
        err("File not found: %s" % serverprops)
        sys.exit(1)

    # make sure level-name is defined
    if 'level-name' not in properties:
        # the server recreates missing properties with default values,
        # so try to run the server and then check again
        msg("Generating server files")
        runMinecraft(args.path, args.command, mcoutput)
        properties = parseConfig(serverprops)
        if 'level-name' not in properties:
            err("Property 'level-name' is not defined: %s" % serverprops)
            sys.exit(1)

    # figure out path to level.dat and backup file
    world = os.path.join(args.path, properties['level-name'])
    level = os.path.join(world, "level.dat")
    levelbak = os.path.join(world, "level.dat.explorebackup")

    # start and stop server if level.dat doesn't exist
    if not os.path.isfile(level):
        msg("Generating server files")
        runMinecraft(args.path, args.command, mcoutput)

    # warn the user if the EULA hasn't been accepted
    if not checkEulaAccepted(args.path):
        err("You have not agreed to the Minecraft End User License Agreement: %s" % (eula))
        sys.exit(1)

    # make sure level.dat exists
    if not os.path.isfile(level):
        err("File not found: %s" % level)
        sys.exit(1)

    # make sure dimension is defined
    if dimension != "minecraft:overworld" and dimension not in getDimensions(level):
        err("Dimension not defined in %s: '%s'" % ("level.dat", dimension))
        sys.exit(1)

    # figure out full path to region folders
    regionfolder = os.path.join(args.path, regionfolder)
    origfolder = os.path.join(args.path, "world", "region")
    origfolderbak = os.path.join(args.path, "world", basenames['regionbak'])

    # back up level.dat
    originalspawn = getSpawn(level)
    msg("Backing up %s with spawn of %d, %d, %d:" % ("level.dat", *originalspawn))
    msg("  '%s' -> '%s'" % (level, levelbak))
    shutil.copyfile(level, levelbak)

    # replace overworld region folder with dimension region folder
    if not os.path.samefile(regionfolder, origfolder):
        if not os.path.isdir(origfolder):
            err("Directory not found: %s" % origfolder)
            sys.exit(1)
        elif not os.path.isdir(os.path.dirname(regionfolder)):
            err("Directory not found: %s" % regionfolder)
            sys.exit(1)
        msg("Moving %s region folder:" % "minecraft:overworld")
        msg("  '%s' -> '%s'" % (origfolder, origfolderbak))
        os.rename(origfolder, origfolderbak)
        msg("Moving %s region folder:" % dimension)
        msg("  '%s' -> '%s'" % (regionfolder, origfolder))
        if not os.path.isdir(regionfolder):
            os.mkdir(regionfolder)
        os.rename(regionfolder, origfolder)

    # set generator settings for dimension
    if dimension != "minecraft:overworld":
        setDimension(level, dimension)

    # figure out origin
    if args.xorigin is None: args.xorigin = originalspawn[0]
    if args.zorigin is None: args.zorigin = originalspawn[2]

    # move the origin to the nearest valid center point
    # this will be a region or chunk center, the center of a region or chunk border,
    # or the corner of a region or chunk, depending on the specified dimensions
    # this is not strictly necessary when measuring in chunks, but doesn't hurt
    xoffset = (xsize % 2) * (multiplier / 2)
    zoffset = (zsize % 2) * (multiplier / 2)
    args.xorigin = int(round(float(args.xorigin + xoffset) / float(multiplier))) * multiplier - xoffset
    args.zorigin = int(round(float(args.zorigin + zoffset) / float(multiplier))) * multiplier - zoffset
    msg("Snapped origin to %d, %d" % (args.xorigin, args.zorigin))

    # the total size of spawn chunks along the x/z axis in blocks
    #
    # there are 25x25 spawn chunks (400x400 blocks), however:
    # trees and snow only generate in the middle 24x24 chunks (384x384 blocks)
    # and in 1.16+ biomes only generate in the middle 23x23 chunks (368x368 blocks)
    #
    # partially generate snow/trees/biomes:
    #spawnsize = 400
    # minecraft 1.15 or older:
    #spawnsize = 384
    # minecraft 1.16 and newer:
    spawnsize = 368

    # figure out the number of blocks in xsize and zsize
    xblocks = xsize * multiplier - spawnsize - 16
    zblocks = zsize * multiplier - spawnsize - 16
    msg("Size of area to generate: %dx%d blocks" % (xblocks + spawnsize, zblocks + spawnsize))

    # loop through a grid of spawn points within the requested range,
    # starting and stopping the server for each one.
    xiterations = int(math.ceil(xblocks / spawnsize) + 1)
    ziterations = int(math.ceil(zblocks / spawnsize) + 1)
    for xcount in range(0, xiterations):
        x = args.xorigin - xblocks / 2 + xcount * spawnsize
        if x > args.xorigin + xblocks / 2: x = args.xorigin + xblocks / 2
        for zcount in range(0, ziterations):
            z = args.zorigin - zblocks / 2 + zcount * spawnsize
            if z > args.zorigin + zblocks / 2: z = args.zorigin + zblocks / 2
            msg("Setting spawn to %d, %d" % (x, z))
            setSpawn(level, (int(x), 64, int(z)))
            runMinecraft(args.path, args.command, mcoutput)

    # restore dimension
    if not os.path.samefile(regionfolder, origfolder):
        msg("Restoring %s region folder:" % dimension)
        msg("  '%s' -> '%s'" % (origfolder, regionfolder))
        os.rename(origfolder, regionfolder)
        msg("Restoring %s region folder:" % "minecraft:overworld")
        msg("  '%s' -> '%s'" % (origfolderbak, origfolder))
        os.rename(origfolderbak, origfolder)

    # restore level.dat
    msg("Restoring %s with spawn of %d, %d, %d:" % ("level.dat", *originalspawn))
    msg("  '%s' -> '%s'" % (levelbak, level))
    os.remove(level)
    os.rename(levelbak, level)

def getSpawn(level):
    """Gets the spawn point from level.dat"""
    data = nbt.NBTFile(level,'rb')["Data"]
    return (data['SpawnX'].value, data['SpawnY'].value, data['SpawnZ'].value)

def setSpawn(level, coords):
    """Sets the spawn point in level.dat"""
    f = nbt.NBTFile(level,'rb')
    (f["Data"]["SpawnX"].value, f["Data"]["SpawnY"].value, f["Data"]["SpawnZ"].value) = coords
    f.write_file(level)

def getDimensions(level):
    """Gets the generator settings for a dimension in level.dat"""
    data = nbt.NBTFile(level,'rb')["Data"]
    return [ key for key in data["WorldGenSettings"]["dimensions"] ]

def setDimension(level, dim):
    """Copies the generator settings for a dimension in level.dat to the overworld"""
    f = nbt.NBTFile(level,'rb')
    f["Data"]["WorldGenSettings"]["dimensions"]["minecraft:overworld"] = f["Data"]["WorldGenSettings"]["dimensions"][dim]
    f.write_file(level)

def runMinecraft(path, command, outstream):
    """Starts and stops the minecraft server"""
    mc = subprocess.Popen(command.split(), cwd=path, stdin=subprocess.PIPE, stdout=outstream, universal_newlines=True)
    mc.communicate("stop\n")
    if mc.wait() != 0:
        err()
        err("Command failed: '%s'" % command.replace("'", "\\'"))
        if outstream != sys.stdout:
            err("Check %s for errors" % os.path.join(path, 'logs', 'latest.log'))

        sys.exit(1)

def parseConfig(filename):
    """Parses server.properties and returns a dict of property keys and values."""
    properties = {}
    f = open(filename, 'r')
    for line in f:
        line = line.strip()
        if not line.startswith("#"):
            (key, sep, val) = line.partition("=")
            properties[key] = val
    return properties

def checkEulaAccepted(eula):
    if os.path.isfile(eula):
        with open(eula, "r") as file:
            if "eula=false\n" in file:
                return False
    return True

if __name__ == "__main__":
    main()

