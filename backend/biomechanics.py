"""Micro-CT-derived NeuroMechFly body, integrated by MuJoCo (no scripted pose path).

The motor-population-to-CPG adapter is an engineered interface, not an identified
muscle model. All free-body positions/rotations result from physical integration.
"""
from pathlib import Path
import json,hashlib,math
import numpy as np
import mujoco
import flygym
from flygym import Simulation
from flygym.anatomy import BodySegment,ContactBodiesPreset
from flygym.compose import FlatGroundWorld
from flygym.utils.math import Rotation3D
from flygym_demo.complex_terrain import (
    HybridTurningController,HybridControllerObservation,LocomotionAction,
    PreprogrammedSteps,apply_locomotion_action,make_locomotion_fly,
)

class BiomechanicalFly:
    PHYSICS_DT=.0001
    CONTROL_DT=.001
    def __init__(self):
        self.steering_gain=2.0
        self.fly=make_locomotion_fly(name='eeg_fly',colorize=True)
        world=FlatGroundWorld()
        world.add_fly(self.fly,[0,0,.8],Rotation3D('quat',[1,0,0,0]),
                      bodysegs_with_ground_contact=ContactBodiesPreset.TIBIA_TARSUS_ONLY,
                      add_ground_contact_sensors=False)
        self.sim=Simulation(world,timestep=self.PHYSICS_DT)
        self.steps=PreprogrammedSteps()
        self.dofs=self.fly.get_actuated_jointdofs_order('position')
        self.controller=HybridTurningController(timestep=self.CONTROL_DT,
            preprogrammed_steps=self.steps,output_dof_order=self.dofs)
        self.thorax=self.fly.get_bodysegs_order().index(BodySegment('c_thorax'))
        self.geom_ids=np.flatnonzero(self.sim.mj_model.geom_type==mujoco.mjtGeom.mjGEOM_MESH)
        self.reset()

    def reset(self):
        self.sim.reset();self.controller.reset(seed=0)
        action=LocomotionAction(self.steps.default_pose_by_dof_order(self.dofs),np.ones(6,dtype=bool))
        apply_locomotion_action(self.sim,self.fly.name,action);self.sim.warmup()
        self.elapsed=0.;self.path=[];self.distance=0.;self.signals=np.ones(2)
        self.previous_position=self.position().copy();self.initial_position=self.position().copy()
        self.joint_work=0.;self.last_contacts=0

    def position(self):return self.sim.get_body_positions(self.fly.name)[self.thorax]

    def advance(self,motor_normalized,duration=.005):
        # Higher ipsilateral motor-population activity shortens that side's CPG
        # step amplitude. This adapter follows the steering convention; it is
        # intentionally documented separately from the measured synapse graph.
        rates=np.array([motor_normalized['L'],motor_normalized['R']])
        self.signals=np.clip(1.0-.65*self.steering_gain*rates,.25,1.0)
        return self.advance_signals(self.signals,duration)

    def advance_signals(self,signals,duration=.005):
        signals=np.asarray(signals,dtype=float)
        for _ in range(round(duration/self.CONTROL_DT)):
            obs=HybridControllerObservation.from_sim(self.sim,self.fly.name)
            action=self.controller.step(signals,obs)
            apply_locomotion_action(self.sim,self.fly.name,action)
            mujoco.mj_step(self.sim.mj_model,self.sim.mj_data,nstep=round(self.CONTROL_DT/self.PHYSICS_DT))
        self.elapsed+=duration
        p=self.position().copy()
        self.distance+=float(np.linalg.norm((p-self.previous_position)[:2]));self.previous_position=p
        self.path.append([float(p[0]),float(p[1]),float(p[2])]);self.path=self.path[-2000:]
        if not np.isfinite(self.sim.mj_data.qpos).all():raise RuntimeError('Non-finite MuJoCo state')
        return self.state()

    def state(self):
        data=self.sim.mj_data
        position=self.position()
        q=self.sim.get_body_rotations(self.fly.name)[self.thorax]
        w,x,y,z=q
        yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
        upright=1-2*(x*x+y*y)
        return dict(position=position.round(6).tolist(),quaternion=q.round(7).tolist(),
                    heading=yaw,physics_time=round(self.elapsed,6),upright=float(upright),
                    contacts=int(data.ncon),signals=self.signals.round(5).tolist(),distance=round(self.distance,5),
                    joint_angles=self.sim.get_joint_angles(self.fly.name).round(6).tolist(),
                    geometry_positions=data.geom_xpos[self.geom_ids].round(6).tolist(),
                    geometry_rotations=data.geom_xmat[self.geom_ids].round(7).tolist(),path=self.path)

    def geometry(self):
        model=self.sim.mj_model;meshes={};geoms=[]
        for geom_id in self.geom_ids:
            mesh_id=int(model.geom_dataid[geom_id])
            if mesh_id not in meshes:
                va=int(model.mesh_vertadr[mesh_id]);vn=int(model.mesh_vertnum[mesh_id])
                fa=int(model.mesh_faceadr[mesh_id]);fn=int(model.mesh_facenum[mesh_id])
                vertices=model.mesh_vert[va:va+vn]
                faces=model.mesh_face[fa:fa+fn]
                assert int(faces.max())<vn
                meshes[mesh_id]=dict(vertices=vertices.round(7).ravel().tolist(),faces=faces.ravel().tolist())
            material_id=int(model.geom_matid[geom_id])
            rgba=model.mat_rgba[material_id] if material_id>=0 else model.geom_rgba[geom_id]
            geoms.append(dict(mesh_id=mesh_id,name=mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,int(geom_id)),
                              rgba=rgba.tolist()))
        assets=Path(flygym.assets_dir)/'model/neuromechfly'
        hashes={str(p.relative_to(assets)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in assets.rglob('*') if p.is_file()}
        return dict(meshes=meshes,geoms=geoms,
                    provenance=dict(model='NeuroMechFly / FlyGym 2.1.0',engine='MuJoCo '+mujoco.__version__,
                    morphology='micro-CT-derived adult female Drosophila, simplified original meshes',
                    paper='https://doi.org/10.1038/s41592-024-02497-y',
                    source='https://github.com/NeLy-EPFL/flygym/tree/v2.1.0',
                    physics_timestep=self.PHYSICS_DT,controller_timestep=self.CONTROL_DT,
                    nq=model.nq,nv=model.nv,actuators=model.nu,leg_position_actuators=len(self.dofs),
                    units='mm, mg, s; gravity -9810 mm/s²',asset_sha256=hashes,
                    controller='Published FlyGym hybrid CPG + retraction/stumbling corrections; engineered motor-population amplitude interface'))
