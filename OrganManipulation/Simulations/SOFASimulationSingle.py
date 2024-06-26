import os
script_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['SOFA_ROOT'] = script_dir + '/../../qt-loadable-modules'

import slicer
from qt import QObject, QTimer

import Sofa
import SofaRuntime

def createScene(rootNode, parameterNode):

    from stlib3.scene import MainHeader, ContactHeader
    from stlib3.solver import DefaultSolver
    from stlib3.physics.deformable import ElasticMaterialObject
    from stlib3.physics.rigid import Floor
    from splib3.numerics import Vec3

    MainHeader(rootNode, plugins=[
        "Sofa.Component.IO.Mesh",
        "Sofa.Component.LinearSolver.Direct",
        "Sofa.Component.LinearSolver.Iterative",
        "Sofa.Component.Mapping.Linear",
        "Sofa.Component.Mass",
        "Sofa.Component.ODESolver.Backward",
        "Sofa.Component.Setting",
        "Sofa.Component.SolidMechanics.FEM.Elastic",
        "Sofa.Component.StateContainer",
        "Sofa.Component.Topology.Container.Dynamic",
        "Sofa.Component.Visual",
        "Sofa.GL.Component.Rendering3D",
        "Sofa.Component.AnimationLoop",
        "Sofa.Component.Collision.Detection.Algorithm",
        "Sofa.Component.Collision.Detection.Intersection",
        "Sofa.Component.Collision.Geometry",
        "Sofa.Component.Collision.Response.Contact",
        "Sofa.Component.Constraint.Lagrangian.Solver",
        "Sofa.Component.Constraint.Lagrangian.Correction",
        "Sofa.Component.LinearSystem",
        "Sofa.Component.MechanicalLoad",
        "MultiThreading",
        "Sofa.Component.SolidMechanics.Spring",
        "Sofa.Component.Constraint.Lagrangian.Model",
        "Sofa.Component.Mapping.NonLinear",
        "Sofa.Component.Topology.Container.Constant",
        "Sofa.Component.Topology.Mapping",
        "Sofa.Component.Engine.Select",
        "Sofa.Component.Constraint.Projective",
        "SofaIGTLink"
    ], dt=parameterNode.dt, gravity=parameterNode.getGravityVector())

    rootNode.addObject('VisualStyle', displayFlags='showVisualModels showForceFields')
    rootNode.addObject('BackgroundSetting', color=[0.8, 0.8, 0.8, 1])
    rootNode.addObject('DefaultAnimationLoop', name="FreeMotionAnimationLoop", parallelODESolving=True)
    rootNode.addObject('iGTLinkClient', name="iGTLClient", sender=True, hostname="127.0.0.1", port=parameterNode.serverPort)

    meshNode = rootNode.addChild('Mesh')
    meshNode.addObject('EulerImplicitSolver', firstOrder=False, rayleighMass=0.1, rayleighStiffness=0.1)
    meshNode.addObject('SparseLDLSolver', name="precond", template="CompressedRowSparseMatrixd", parallelInverseProduct=True)
    meshNode.addObject('MeshVTKLoader', name="loader", filename=parameterNode.modelNodeFileName)
    meshNode.addObject('TetrahedronSetTopologyContainer', name="Container", src="@loader")
    meshNode.addObject('TetrahedronSetTopologyModifier', name="Modifier")
    meshNode.addObject('MechanicalObject', name="mstate", template="Vec3f")
    meshNode.addObject('TetrahedronFEMForceField', name="FEM", youngModulus=1.5, poissonRatio=0.45, method="large")
    meshNode.addObject('MeshMatrixMass', totalMass=1)
    meshNode.addObject('iGTLinkPolyDataMessage', name="SOFAMesh", iGTLink="@../iGTLClient",
                       points="@mstate.position",
                       enableIndices=False,
                       enableEdges=False,
                       enableTriangles=False,
                       enableTetra=False,
                       enableHexa=False)

    fixedROI = meshNode.addChild('FixedROI')
    fixedROI.addObject('BoxROI', template="Vec3", box=parameterNode.getBoundaryROI(), #box=[0, -170, 0, 48, -80, -300],#, 0, -220, 0, 30, -170, -300],
                       drawBoxes=True, position="@../mstate.rest_position", name="FixedROI", computeTriangles=False,
                       computeTetrahedra=False, computeEdges=False)
    fixedROI.addObject('FixedConstraint', indices="@FixedROI.indices")

    collisionNode = meshNode.addChild('Collision')
    collisionNode.addObject('TriangleSetTopologyContainer', name="Container")
    collisionNode.addObject('TriangleSetTopologyModifier', name="Modifier")
    collisionNode.addObject('Tetra2TriangleTopologicalMapping', input="@../Container", output="@Container")

class SimulationWorker(QObject):
    def __init__(self, parameterNode, parent=None):
        super(SimulationWorker, self).__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.simulateStep)
        self.parameterNode = parameterNode
        self._sceneUp = False

    def setupScene(self):
        self.root = Sofa.Core.Node()
        createScene(self.root, self.parameterNode)
        Sofa.Simulation.init(self.root)
        self._sceneUp = True

    def startSimulation(self):
        if self._sceneUp is not True:
            self.setupScene()
        else:
            Sofa.Simulation.reset(self.root)
        self.currentStep = 0
        # Adjust the timer interval as needed
        self.timer.start(0)  # 1000 ms (1 second) interval

    def simulateStep(self):
        if self.currentStep < self.parameterNode.totalSteps:
            Sofa.Simulation.animate(self.root, self.root.dt.value)
            self.currentStep += 1
        else:
            self.timer.stop()  # Stop the timer after completing the simulation steps

class SimulationController:
    def __init__(self, parameterNode):
        self.worker = SimulationWorker(parameterNode)
        # In Slicer, QTimer can be used without moving to a new QThread
        # but you can use slicer.app.processEvents() if needed for GUI updates

    def start(self):
        self.worker.startSimulation()

