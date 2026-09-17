import json,math,unittest
from pathlib import Path
import numpy as np
from backend.manc_network import MANCNetwork,MeasuredDynamics,ROOT
from backend.biomechanics import BiomechanicalFly
from backend.real_simulation import RealSimulation
from backend.eeg_decoder import prepare,filter_eeg

class MeasuredPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph=MANCNetwork();cls.eeg,cls.metrics=prepare();cls.body=BiomechanicalFly()

    def test_01_every_retained_edge_matches_official_release(self):
        import pandas as pd
        path=ROOT/'data/manc/raw/traced-connections.csv'
        if not path.exists():self.skipTest('Run scripts/download_manc.py to verify raw publisher files')
        official=pd.read_csv(path);official=official[official.weight>=5]
        ids=np.array([int(n['node_id']) for n in self.graph.neurons])
        np.testing.assert_array_equal(official.bodyId_pre,ids[self.graph.sources])
        np.testing.assert_array_equal(official.bodyId_post,ids[self.graph.targets])
        np.testing.assert_array_equal(official.weight,self.graph.counts)
        self.assertEqual(len(official),1360021);self.assertEqual(len(ids),23188)

    def test_02_input_and_motor_annotations_are_real_ids(self):
        import pandas as pd
        g=self.graph
        for side,body in [('L','10126'),('R','10118')]:
            n=g.neurons[g.inputs[side]]
            self.assertEqual(n['node_id'],body);self.assertEqual(n['cell_type'],'DNa02');self.assertEqual(n['side'],side)
        motor_ids={int(g.neurons[i]['node_id']) for group in g.motors.values() for i in group}
        self.assertEqual(len(motor_ids),247)
        path=ROOT/'data/manc/raw/leg-motor-neurons.csv'
        if path.exists():
            table=pd.read_csv(path).set_index('bodyid')
            self.assertTrue(motor_ids.issubset(table.index))
            for side,group in g.motors.items():
                for i in group:self.assertEqual(table.loc[int(g.neurons[i]['node_id'])].soma_side,side+'HS')

    def test_03_visual_coordinates_are_common_affine_of_source(self):
        nodes=self.graph.nodes
        raw=np.array([n['raw_position'] for n in nodes]);shown=np.array([[n['x'],n['y'],n['z']] for n in nodes])
        expected=raw[:,[0,2,1]]*[1,1,-1]
        ratio=np.linalg.norm(shown[1:]-shown[0],axis=1)/np.linalg.norm(expected[1:]-expected[0],axis=1)
        np.testing.assert_allclose(ratio,ratio[0],rtol=1e-10)
        json.dumps(self.graph.payload(),allow_nan=False)

    def test_04_propagation_is_delayed_and_side_specific(self):
        for side,other in [('L','R'),('R','L')]:
            n=MeasuredDynamics(self.graph);n.step(side)
            self.assertGreater(n.x[self.graph.inputs[side]],0)
            self.assertEqual(n.motor_activity()[side],0)
            for _ in range(99):n.step(side)
            self.assertGreater(n.motor_activity()[side],5*n.motor_activity()[other])

    def test_05_cut_synapses_removes_steering_influence(self):
        results={}
        for side,cut in [(None,False),('L',False),('R',False),('L',True),('R',True)]:
            self.body.reset();n=MeasuredDynamics(self.graph);n.lesion=cut
            for _ in range(200):
                m=n.step(side);state=self.body.advance({s:m[s]/self.graph.motor_scale for s in ('L','R')})
                self.assertGreater(state['upright'],.9)
                self.assertTrue(np.isfinite(self.body.sim.mj_data.qpos).all())
            results[(side,cut)]=(self.body.sim.mj_data.qpos.copy(),state)
        np.testing.assert_array_equal(results[(None,False)][0],results[('L',True)][0])
        np.testing.assert_array_equal(results[(None,False)][0],results[('R',True)][0])
        self.assertGreater(results[('L',False)][1]['heading']-results[(None,False)][1]['heading'],.3)
        self.assertLess(results[('R',False)][1]['heading']-results[(None,False)][1]['heading'],-.3)

    def test_06_mujoco_geometry_and_physical_state(self):
        geom=self.body.geometry();self.assertEqual(geom['provenance']['leg_position_actuators'],42)
        self.assertEqual(geom['provenance']['actuators'],48);self.assertEqual(len(geom['geoms']),69)
        for m in geom['meshes'].values():self.assertLess(max(m['faces']),len(m['vertices'])//3)
        self.body.reset();before=self.body.sim.mj_data.qpos.copy()
        for _ in range(20):self.body.advance({'L':0,'R':0})
        self.assertGreater(np.linalg.norm(self.body.sim.mj_data.qpos-before),.01)
        self.assertGreater(self.body.sim.mj_data.ncon,0)

    def test_07_actual_eeg_prediction_drives_input_and_pause(self):
        sim=RealSimulation(self.graph,self.eeg);sim.control(dict(action='pause'))
        before=sim.payload();sim.step();self.assertEqual(before,sim.payload())
        sim.running=True
        # The first decoded RIGHT trial is taken chronologically, not by accuracy.
        sim.index=int(np.flatnonzero(self.eeg['predictions']==1)[0])
        for _ in range(81):sim.step()
        self.assertEqual(sim.command,'RIGHT');self.assertEqual(sim.payload()['input_body_id'],10118)
        self.assertGreater(sim.net.motor_activity()['R'],sim.net.motor_activity()['L'])
        self.assertAlmostEqual(sim.body.elapsed,.405,places=8)
        sim.control(dict(action='lesion',value=True))
        for _ in range(5):sim.step()
        self.assertEqual(sim.net.motor_activity(),dict(L=0.,R=0.))

    def test_09_cut_mid_turn_matches_zero_input_from_same_body_state(self):
        driven=RealSimulation(self.graph,self.eeg)
        reference=RealSimulation(self.graph,self.eeg)
        for _ in range(70):driven.step();reference.step()
        np.testing.assert_array_equal(driven.body.sim.mj_data.qpos,reference.body.sim.mj_data.qpos)
        driven.control(dict(action='lesion',value=True))
        self.assertEqual(driven.command,'HOLD')
        self.assertEqual(driven.payload()['cut_turn_deg'],0)
        for _ in range(50):
            driven.step()
            reference.body.advance(dict(L=0.,R=0.),driven.BODY_DT)
            np.testing.assert_array_equal(driven.body.sim.mj_data.qpos,reference.body.sim.mj_data.qpos)
            self.assertEqual(driven.net.motor_activity(),dict(L=0.,R=0.))
            np.testing.assert_array_equal(driven.body.signals,[1.,1.])
        self.assertGreater(abs(driven.cut_turn),.01)
        self.assertAlmostEqual(driven.payload()['cut_elapsed'],.25)

    def test_08_causal_eeg_filter_does_not_see_future(self):
        X=np.random.default_rng(5).normal(size=(2,22,1000))*1e-6
        np.testing.assert_allclose(filter_eeg(X)[:,:,:500],filter_eeg(X[:,:,:500]),atol=1e-15)

if __name__=='__main__':unittest.main()
