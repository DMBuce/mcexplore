#!/usr/bin/python

# mcexplore.py, by similardilemma
# Released under the Creative Commons Attribution-ShareAlike license:
# http://creativecommons.org/licenses/by-sa/3.0/

from __future__ import print_function

import os
import sys
import shutil
import optparse
import subprocess
import math
import time
import signal

# https://stackoverflow.com/a/11270665
try:
    from subprocess import DEVNULL
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

def msg(message="", file=sys.stdout):
    print(message, file=file)

def err(message=""):
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

def sighandler(signum, frame):
    sys.exit(1)

def main():
    # define vars
    prog = os.path.basename(sys.argv[0])
    version = "%prog 1.5"
    usage = "Usage: %prog [options] <xsize> [zsize]"
    description = """\
Uses a Minecraft server to pregenerate a square section of the world.
<xsize> and <zsize> are in units of chunks (16x16 blocks) by default,
and must be greater than 25 chunks. If only <xsize> is specified, it
is also used as the value for <zsize>.
"""

    # set signal handler
    signal.signal(signal.SIGTERM, sighandler)

    # parse options
    parser = optparse.OptionParser(version=version, usage=usage, description=description)
    parser.add_option(
        "-v", "--verbose", dest="verbose", default=False,
        action="store_true",
        help="Show minecraft server output."
    )
    parser.add_option(
        "-p", "--path", dest="path", default=".",
        help="The working directory to use when running the server. Default: The current directory."
    )
    parser.add_option(
        "-c", "--command", dest="command", default="java -jar minecraft_server.jar nogui",
        help="The command used to start the server. Default: 'java -jar minecraft_server.jar nogui'."
    )
    parser.add_option(
        "-x", dest="xorigin", default=None,
        type="int",
        help="The X offset to generate land around. Default: The server's spawn point."
    )
    parser.add_option(
        "-z", dest="zorigin", default=None,
        type="int",
        help="The Z offset to generate land around. Default: the server's spawn point."
    )
    parser.add_option(
        "-r", "--regions", dest="regions", default=False,
        action="store_true",
        help="Use units of regions (32x32 chunks) instead of chunks for <xsize> and <zsize>"
    )
    (options, args) = parser.parse_args()

    # validate args
    if len(args) == 0:
        parser.print_usage(file=sys.stderr)
        err("%s: error: argument xsize: no size given" % prog)
        sys.exit(1)
    elif not args[0].isdigit():
        parser.print_usage(file=sys.stderr)
        err("%s: error: argument xsize: invalid integer value: '%s'" % (prog, args[0].replace("'", "\\'")))
        sys.exit(1)
    elif len(args) > 1 and not args[1].isdigit():
        parser.print_usage(file=sys.stderr)
        err("%s: error: argument zsize: invalid integer value: '%s'" % (prog, args[0].replace("'", "\\'")))
        sys.exit(1)

    # parse args
    xsize = int(args[0])
    zsize = int(args[1]) if len(args) > 1 else int(args[0])

    # figure out multiplier
    multiplier = 512 if options.regions else 16

    # sanity checks
    #
    # make sure sizes are reasonable
    if options.regions and xsize < 2:
        err("xsize too small: %s" % xsize)
        err()
        err("The area to generate must be 2x2 regions or larger.")
        sys.exit(1)
    elif options.regions and zsize < 2:
        err("zsize too small: %s" % zsize)
        err()
        err("The area to generate must be 2x2 regions or larger.")
        sys.exit(1)
    # permanently loaded spawn area is 25x25 chunks
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

    # do a dry run if the server hasn't started at least once
    if not os.path.isfile(os.path.join(options.path, 'server.properties')):
        msg("Generating world and server.properties")
        runMinecraft(options.path, options.command, options.verbose)

    # use server.properties to figure out path to world folder
    properties = parseConfig(os.path.join(options.path, 'server.properties'))
    world = os.path.join(options.path, properties['level-name'])

    # figure out path to level.dat and backup file
    level = os.path.join(world, "level.dat")
    levelbak = os.path.join(world, "level.dat.explorebackup")

    # bail if a backup already exists
    if os.path.isfile(levelbak):
        err("Backup of level.dat already exists: %s" % levelbak)
        err()
        err("Either %s failed, was interrupted or is still running." % prog)
        err("Restore or delete the backup and try again.")
        sys.exit(1)

    # get original spawn point
    originalspawn = getSpawn(level)

    try:
        # back up level.dat
        shutil.copyfile(level, levelbak)

        # figure out origin
        if options.xorigin is None: options.xorigin = originalspawn[0]
        if options.zorigin is None: options.zorigin = originalspawn[2]

        # move the origin to the nearest valid center point
        # this will be a region or chunk center, the center of a region or chunk border,
        # or the corner of a region or chunk, depending on the specified dimensions
        # this is not strictly necessary when measuring in chunks, but doesn't hurt
        xoffset = (xsize % 2) * (multiplier / 2)
        zoffset = (zsize % 2) * (multiplier / 2)
        options.xorigin = int(round(float(options.xorigin + xoffset) / float(multiplier))) * multiplier - xoffset
        options.zorigin = int(round(float(options.zorigin + zoffset) / float(multiplier))) * multiplier - zoffset
        msg("Snapped origin to %d, %d" % (options.xorigin, options.zorigin))

        # loop through a grid of spawn points within the given range, starting and stopping the server for each one
        # note that the server generated spawn point is 400x400 meters (25x25 chunks), but it does not generate
        # trees or snow outside of a 384x384 meter box.
        spawnsize = 384.0
        # normalize xsize and zsize so that they're measured in blocks
        xsize = xsize * multiplier - spawnsize - 16
        zsize = zsize * multiplier - spawnsize - 16
        msg("Size of area to generate: %dx%d blocks" % (xsize + spawnsize, zsize + spawnsize))
        xiterations = int(math.ceil(xsize / spawnsize) + 1)
        ziterations = int(math.ceil(zsize / spawnsize) + 1)
        for xcount in range(0, xiterations):
            x = options.xorigin - xsize / 2 + xcount * spawnsize
            if x > options.xorigin + xsize / 2: x = options.xorigin + xsize / 2
            for zcount in range(0, ziterations):
                z = options.zorigin - zsize / 2 + zcount * spawnsize
                if z > options.zorigin + zsize / 2: z = options.zorigin + zsize / 2
                msg("Setting spawn to %d, %d" % (x, z))
                setSpawn(level, (int(x), 64, int(z)))
                runMinecraft(options.path, options.command, options.verbose)
    finally:
        # restore the old spawn point
        msg("Restoring original spawn of %d, %d, %d" % originalspawn)
        #os.remove(level)
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
    if mc.wait() != 0:
        err()
        err("Command exited with failure status: `%s`" % command.replace('`', '\\`'))
        sys.exit(1)

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

