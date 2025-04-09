import unittest
from datetime import datetime, timedelta
from solar_sim import PowerDevice, SimTime, SolarArray, SolarBattery, Grid, EnergyLoad

def get_example_sim_time(time_diff_sec=60*15) -> SimTime:
    st = SimTime()
    st.sim_time = datetime(2025,1,2,5,1)
    st.sim_time = st.sim_time + timedelta(seconds=time_diff_sec)
    return st

class TestSimTime(unittest.TestCase):
    def test_initialization(self):
        sim_time = SimTime()
        self.assertLess(sim_time.sim_time, datetime(2000,1,1))
        self.assertLess(sim_time.prev_time, datetime(2000,1,1))
        self.assertLess(sim_time.prev_time, sim_time.sim_time)

    def test_get_dt(self):
        sim_time = SimTime()
        sim_time.sim_time = datetime(2025, 1, 1, 12, 0, 0)
        sim_time.sim_time = datetime(2025, 1, 1, 13, 0, 0)
        dt = sim_time.get_dt()
        self.assertEqual(dt.total_seconds(), 3600)  # 1 hour difference

        sim_time.sim_time = sim_time.sim_time + timedelta(seconds=60)
        self.assertEqual(sim_time.get_dt().total_seconds(), 60)


class TestSolarArray(unittest.TestCase):
    def test_initialization(self):
        solar = SolarArray(panel_num=10)
        solar.set_time_obj(get_example_sim_time())
        self.assertEqual(solar.panel_num, 10)
        self.assertEqual(solar.generated_energy_wh, 0)
        self.assertEqual(solar.lifetime_energy_wh, 0)

    def test_solar_energy_generation(self):
        solar = SolarArray(panel_num=5)
        generated_energy = solar.set_solar_generated_energy_wh(100)  # 100 Wh per panel
        self.assertEqual(generated_energy, 500)  # 5 panels * 100 Wh = 500 Wh
        self.assertEqual(solar.generated_energy_wh, 500)

    def test_get_generated_energy(self):
        solar = SolarArray(panel_num=4)
        solar.set_solar_generated_energy_wh(50)  # 4 panels * 50 Wh = 200 Wh
        retrieved_energy = solar.get_generated_energy_wh()
        self.assertEqual(retrieved_energy, 200)
        self.assertEqual(solar.generated_energy_wh, 0)  # Should be cleared after retrieval
        self.assertEqual(solar.lifetime_energy_wh, 200)  # Lifetime should increase

    def test_store_energy(self):
        solar = SolarArray(panel_num=5)
        stored_energy = solar.store_energy(500)  # Solar panels cannot store energy
        self.assertEqual(stored_energy, 0.0)

    def test_get_energy(self):
        solar = SolarArray(panel_num=3)
        solar.set_solar_generated_energy_wh(100)  # 3 panels * 100 Wh = 300 Wh
        energy_requested = solar.get_energy(150)  # Request 150 Wh
        self.assertEqual(energy_requested, 150)
        self.assertEqual(solar.generated_energy_wh, 150)  # Remaining energy after request
        self.assertEqual(solar.lifetime_energy_wh, 150)  # Lifetime should accumulate

    def test_reset_memory(self):
        solar = SolarArray(panel_num=2)
        solar.set_solar_generated_energy_wh(200)  # 2 * 200 = 400 Wh
        solar.get_generated_energy_wh()  # Clear energy
        solar.reset_memory()
        self.assertEqual(solar.generated_energy_wh, 0)
        self.assertEqual(solar.lifetime_energy_wh, 0)

class TestSolarBattery(unittest.TestCase):
    def setUp(self):
        self.battery = SolarBattery(usable_energy_kwh=10)
        self.battery.set_time_obj(get_example_sim_time())
    
    def test_initial_soc(self):
        self.assertAlmostEqual(self.battery.soc, 0.5, places=2)
    
    def test_store_energy(self):
        self.battery.time_obj.sim_time = self.battery.time_obj.sim_time + timedelta(days=1)
        energy_accepted = self.battery.store_energy(500)
        self.assertEqual(energy_accepted, 500)
        self.assertAlmostEqual(self.battery.soc, 0.55, places=2)

    def test_store_all_energy(self):
        self.battery.max_c_rate = 100
        self.battery.time_obj.sim_time = self.battery.time_obj.sim_time + timedelta(days=1)
        energy_accepted = self.battery.store_energy(50000)
        self.assertGreater(energy_accepted, 5000)
        self.assertAlmostEqual(self.battery.soc, 1, places=2)
    
    def test_get_energy(self):
        energy_provided = self.battery.get_energy(500)
        self.assertGreater(energy_provided, 0)
        self.assertAlmostEqual(self.battery.soc, 0.45, places=1)
        self.assertEqual(energy_provided, self.battery.cur_ts_discharge_wh)
        energy_provided2 = self.battery.get_energy(5)
        self.assertEqual(energy_provided+energy_provided2, self.battery.cur_ts_discharge_wh)

    def test_deplete_all_energy(self):
        self.battery.max_c_rate = 100
        energy_provided = self.battery.get_energy(50000)
        self.assertLess(energy_provided, 5000)
        self.assertEqual(self.battery.soc, 0)
        

    def test_get_set_energy(self):
        self.assertEqual(self.battery.cur_ts_discharge_wh, 0)
        self.assertEqual(self.battery.cur_ts_charge_wh, 0)
        energy_provided = self.battery.get_energy(50)
        self.assertEqual(energy_provided, self.battery.cur_ts_discharge_wh)
        energy_stored = self.battery.store_energy(60)
        self.assertEqual(energy_provided, self.battery.cur_ts_discharge_wh)
        self.assertEqual(energy_stored, self.battery.cur_ts_charge_wh)
        self.battery.time_obj.sim_time += timedelta(minutes=15)
        self.battery.store_energy(0) #Reset current timestep counters
        self.assertEqual(self.battery.cur_ts_discharge_wh, 0)
        self.assertEqual(self.battery.cur_ts_charge_wh, 0)

    
    def test_reset_memory(self):
        self.battery.reset_memory()
        self.assertAlmostEqual(self.battery.soc, 0.5, places=2)
        self.assertEqual(self.battery.throughput_wh, 0)
    
class TestGrid(unittest.TestCase):
    def setUp(self):
        self.grid = Grid(initial_credits=50)
        self.grid.set_time_obj(get_example_sim_time())
    
    def test_initial_credits(self):
        self.assertEqual(self.grid.available_credits_dollars, 50)
    
    def test_add_credits(self):
        self.grid.add_credits(10)
        self.assertEqual(self.grid.available_credits_dollars, 60)
    
    def test_use_credits(self):
        used = self.grid.use_credits(20)
        self.assertEqual(used, 20)
        self.assertEqual(self.grid.available_credits_dollars, 30)
    
    def test_purchase_energy(self):
        self.grid.purchase_energy(15)
        self.assertEqual(self.grid.money_spent_dollars, 15)
    
    def test_store_energy(self):
        energy_stored = self.grid.store_energy(1000)
        self.assertEqual(energy_stored, 1000)
    
    def test_get_energy(self):
        energy_retrieved = self.grid.get_energy(1000)
        self.assertEqual(energy_retrieved, 1000)

    def test_get_set_energy(self):
        self.assertEqual(self.grid._cur_ts_export_wh, 0)
        self.assertEqual(self.grid.cur_ts_import_wh, 0)
        energy_stored = self.grid.store_energy(1000)
        energy_retrieved = self.grid.get_energy(1001)
        self.assertEqual(self.grid._cur_ts_export_wh, energy_stored)
        self.assertEqual(self.grid.cur_ts_import_wh, energy_retrieved)
        self.grid.time_obj.sim_time += timedelta(minutes=15)
        self.grid.store_energy(0) #Reset current timestep counters
        self.assertEqual(self.grid._cur_ts_export_wh, 0)
        self.assertEqual(self.grid.cur_ts_import_wh, 0)
    
class TestEnergyLoad(unittest.TestCase):
    def setUp(self):
        self.load = EnergyLoad()
        self.battery = SolarBattery(usable_energy_kwh=10)
        self.grid = Grid(initial_credits=50)
    
    def test_add_energy_usage(self):
        self.load.add_energy_usage(1000)
        self.assertEqual(self.load.energy_usage_wh, 1000)
    
    def test_draw_energy(self):
        self.load.add_energy_usage(1000)
        self.load.draw_energy([self.battery, self.grid])
        self.assertEqual(self.load._remaining_load_wh, 0)
    
    def test_draw_energy_not_fulfilled(self):
        self.load.add_energy_usage(50000)  # Exceeds available energy
        with self.assertRaises(ValueError):
            self.load.draw_energy([self.battery])

if __name__ == "__main__":
    unittest.main()
