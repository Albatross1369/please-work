import click    # package for creating command line interfaces
import numpy as np   #used to deal with array and matrices
import pandas as pd  #for data manipulation and analysis
import logging #module for logging messages in Python
from rich.logging import RichHandler
from tqdm import tqdm
import sys
import yaml
import os
import pyvista as pv
import calc_and_mig_kx_ky_kz
from typing import Union
from mpi4py import MPI
import ctypes

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET",
    format="Rank: " + str(rank) + "/" + str(size) + ": %(asctime)s - %(message)s",
    datefmt="[%X]",
    handlers=[RichHandler()],
)
log = logging.getLogger("rich")

# This code imports several Python libraries and modules, including click, numpy, pandas, logging, rich.logging, tqdm, sys, 
# yaml, os, pyvista, calc_and_mig_kx_ky_kz, typing, and mpi4py.

# It also initializes MPI (Message Passing Interface) using the mpi4py package and sets up a logger for logging messages in
#  Python using the logging module and the rich.logging package.

# The rank and size variables are obtained from the MPI communicator object comm using the Get_rank() and Get_size() methods, 
# respectively.

# Overall, this code sets up the necessary libraries, packages, and configurations for parallel and distributed computing using 
# MPI.

class Mesh:
    def __init__(self, vtk_file_name: Union[str, os.PathLike]):
        log.debug("Reading vtk file %s" % vtk_file_name)
        if os.path.exists(vtk_file_name):
            self.vtk_file_name = vtk_file_name
        else:
            msg = "VTK file %s does not exist" % vtk_file_name
            log.error(msg)
            raise ValueError(msg)
        try:
            self.mesh = pv.read(self.vtk_file_name)
        except Exception as e:
            log.error(e)
            raise ValueError(e)
        log.debug("Reading mesh completed")

        self.npts = self.mesh.n_points
        self.ncells = self.mesh.n_cells
        self.nodes = np.array(self.mesh.points)
        self.tet_nodes = self.mesh.cell_connectivity.reshape((-1, 4))
        log.debug("Generated mesh properties")

    def __str__(self):
        return str(self.mesh)

    def get_centroids(self):
        log.debug("Getting centroids")
        nk = self.tet_nodes[:, 0]
        nl = self.tet_nodes[:, 1]
        nm = self.tet_nodes[:, 2]
        nn = self.tet_nodes[:, 3]
        self.centroids = (
            self.nodes[nk, :]
            + self.nodes[nl, :]
            + self.nodes[nm, :]
            + self.nodes[nn, :]
        ) / 4.0
        log.debug("Getting centroids done!")

    def get_volumes(self):
        log.debug("Getting volumes")
        ntt = len(self.tet_nodes)
        vot = np.zeros((ntt))
        for itet in np.arange(0, ntt):
            n1 = self.tet_nodes[itet, 0]
            n2 = self.tet_nodes[itet, 1]
            n3 = self.tet_nodes[itet, 2]
            n4 = self.tet_nodes[itet, 3]
            x1 = self.nodes[n1, 0]
            y1 = self.nodes[n1, 1]
            z1 = self.nodes[n1, 2]
            x2 = self.nodes[n2, 0]
            y2 = self.nodes[n2, 1]
            z2 = self.nodes[n2, 2]
            x3 = self.nodes[n3, 0]
            y3 = self.nodes[n3, 1]
            z3 = self.nodes[n3, 2]
            x4 = self.nodes[n4, 0]
            y4 = self.nodes[n4, 1]
            z4 = self.nodes[n4, 2]
            pv = (
                (x4 - x1) * ((y2 - y1) * (z3 - z1) - (z2 - z1) * (y3 - y1))
                + (y4 - y1) * ((z2 - z1) * (x3 - x1) - (x2 - x1) * (z3 - z1))
                + (z4 - z1) * ((x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1))
            )
            vot[itet] = np.abs(pv / 6.0)
        self.volumes = vot
        log.debug("Getting volumes done!")

#This code defines a Mesh class that takes a vtk file name as input and generates mesh properties such as nodes, 
# tetrahedral nodes, centroids, and volumes. The get_centroids() method calculates the centroids of the mesh, 
# and the get_volumes() method calculates the volume of each tetrahedral element in the mesh using the formula for the 
# volume of a tetrahedron. The code also includes logging to provide detailed information on the progress of the methods.


class MagneticProperties:
    def __init__(
        self,
        file_name: Union[str, os.PathLike],
        kx: float = 1.0,
        ky: float = 1.0,
        kz: float = 1.0,
    ):
        log.debug("Reading magnetic properties %s" % file_name)
        if os.path.exists(file_name):
            self.file_name = file_name
        else:
            msg = "File %s does not exist" % file_name
            log.error(msg)
            raise ValueError(msg)

        try:
            self.properties = np.load(file_name)
        except Exception as e:
            log.error(e)
            raise ValueError(e)
        log.debug("Reading magnetic properties %s done!" % file_name)

        if len(self.properties.shape) > 0:
            self.n_cells = self.properties.shape[0]
        else:
            msg = "Magnetic properties file %s is incorrect" % file_name
            log.error(msg)
            raise ValueError(msg)

        if self.properties.ndim == 1:
            self.properties = np.expand_dims(self.properties, axis=1)

        if self.properties.shape[1] > 0:
            self.susceptibility = self.properties[:, 0]

        if self.properties.shape[1] > 1:
            self.kx = self.properties[:, 1]
        else:
            self.kx = np.full((self.n_cells,), kx)

        if self.properties.shape[1] > 2:
            self.ky = self.properties[:, 2]
        else:
            self.ky = np.full((self.n_cells,), ky)

        if self.properties.shape[1] > 3:
            self.kz = self.properties[:, 3]
        else:
            self.kz = np.full((self.n_cells,), kz)

        log.debug("Setting all magnetic properties done!")

# This is a class definition for MagneticProperties which represents the magnetic properties of a mesh.

# The constructor takes in a file_name argument (either a string or os.PathLike object) which specifies the path to the 
# file containing the magnetic properties. It also has optional kx, ky, and kz arguments which default to 1.0 if not provided.

# The __init__ method first checks if the file specified by file_name exists. If it does, it loads the file using numpy.load() 
# into the self.properties attribute. If there is an error while loading the file, a ValueError is raised.

# Next, it checks the shape of the self.properties attribute. If it is a 1D array, it is reshaped to a 2D array with a single 
# column. The self.susceptibility, self.kx, self.ky, and self.kz attributes are then set based on the number of columns in 
# self.properties.

# Finally, the __str__ method is not defined in this class.

# Overall, this class seems to be designed to be used in conjunction with the Mesh class to calculate magnetic properties 
# of a 3D mesh.


class MagneticAdjointSolver:
    def __init__(
        self,
        reciever_file_name: Union[str, os.PathLike],
        Bx: float = 4594.8,
        By: float = 19887.1,
        Bz: float = 41568.2,
    ):
        log.debug("Solver initialization started!")
        if os.path.exists(reciever_file_name):
            self.reciever_file_name = reciever_file_name
        else:
            msg = "File %s does not exist" % reciever_file_name
            log.error(msg)
            raise ValueError(msg)

        try:
            self.receiver_locations = pd.read_csv(reciever_file_name)
        except Exception as e:
            log.error(e)
            raise ValueError(e)

        self.Bx = Bx
        self.By = By
        self.Bz = Bz
        self.Bv = np.sqrt(self.Bx**2 + self.By**2 + self.Bz**2)
        self.LX = np.float32(self.Bx / self.Bv)
        self.LY = np.float32(self.By / self.Bv)
        self.LZ = np.float32(self.Bz / self.Bv)
        log.debug("Solver initialization done!")

    def solve(self, mesh: Mesh, magnetic_properties: MagneticProperties):
        log.debug("Solver started for %s" % magnetic_properties.file_name)
        rho_sus = np.zeros((10000000), dtype="float32")
        rho_sus[0 : mesh.ncells] = magnetic_properties.susceptibility

        KXt = np.zeros((10000000), dtype="float32")
        KXt[0 : mesh.ncells] = magnetic_properties.kx

        KYt = np.zeros((10000000), dtype="float32")
        KYt[0 : mesh.ncells] = magnetic_properties.ky

        KZt = np.zeros((10000000), dtype="float32")
        KZt[0 : mesh.ncells] = magnetic_properties.kz

        ctet = np.zeros((10000000, 3), dtype="float32")
        ctet[0 : mesh.ncells] = np.float32(mesh.centroids)

        vtet = np.zeros((10000000), dtype="float32")
        vtet[0 : mesh.ncells] = np.float32(mesh.volumes)

        nodes = np.zeros((10000000, 3), dtype="float32")
        nodes[0 : mesh.npts] = np.float32(mesh.nodes)

        tets = np.zeros((10000000, 4), dtype=int)
        tets[0 : mesh.ncells] = mesh.tet_nodes + 1

        n_obs = len(self.receiver_locations)
        rx_loc = self.receiver_locations.to_numpy()

        obs_pts = np.zeros((1000000, 3), dtype="float32")
        obs_pts[0:n_obs] = np.float32(rx_loc[:, 0:3])

        ismag = True
        rho_sus = rho_sus * self.Bv

        istensor = False

        mig_data = calc_and_mig_kx_ky_kz.calc_and_mig_field(
            rho_sus,
            ismag,
            istensor,
            KXt,
            KYt,
            KZt,
            self.LX,
            self.LY,
            self.LZ,
            nodes,
            tets,
            mesh.ncells,
            obs_pts,
            n_obs,
            ctet,
            vtet,
        )
        log.debug("Solver done for %s" % magnetic_properties.file_name)
        return mig_data[0 : mesh.ncells]


@click.command()
@click.option(
    "--config_file",
    help="Configuration file in YAML format",
    type=click.Path(),
    required=True,
    show_default=True,
)
#This code snippet defines a MagneticAdjointSolver class with a constructor method __init__ and a solve method. 
# The __init__ method takes in a receiver file name and three optional parameters Bx, By, and Bz. It checks whether 
# the receiver file exists, reads the receiver locations from the file, calculates Bv, LX, LY, and LZ using the input 
# Bx, By, and Bz values, and logs a message when the initialization is done.
##Finally, there is a command-line interface defined using the click library that takes in a YAML configuration file as input.

def isciml(config_file: os.PathLike):
    log.debug("Reading configuration file")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as fp:
                config = yaml.safe_load(fp)
        except Exception as e:
            log.error(e)
            raise ValueError(e)
    else:
        msg = "File %s doesn't exist" % config_file
        log.error(msg)
        raise ValueError(msg)

    log.debug("Reading configuration file done!")

    mesh = Mesh(config["vtk_file"])
    mesh.get_centroids()
    mesh.get_volumes()

    properties = MagneticProperties(config["magnetic_properties_file"])
    solver = MagneticAdjointSolver(config["receiver_locations_file"])
    output = solver.solve(mesh, properties)
    # np.save("output.npy", output)
    return 0


if __name__ == "__main__":
    sys.exit(isciml())  # pragma: no cover
