from abc import ABC, abstractmethod
from datetime import time, datetime, timedelta

import pandas as pd

"""
TODO: This simulation needs to run with the system as is, then compare to 
the system modified as requested.
Return aggregate values, but also timeseries... (database?)
"""

class SimTime:
    def __init__(self) -> None:
        self.sim_time = datetime(0,0,0)
        self.prev_time = datetime(0,0,0)
    def get_dt(self):
        dt = self.sim_time - self.prev_time

class PowerDevice(ABC):
    def __init__(self, time_obj:SimTime = SimTime) -> None:
        self.time_obj = time_obj

    @abstractmethod
    def get_generated_energy_wh(self) -> float:
        """
        Return the amount of energy generated (solar) for this time and clear.
        """
        pass

    @abstractmethod
    def store_energy(self, des_energy_wh) -> float:
        """
        Attempt to accept the energy specified to store, 
        reducing as necessary due to efficiency loss.

        Returns the energy accepted.
        """
        pass

    @abstractmethod
    def store_energy_transient(self, des_energy_wh) -> float:
        """
        Attempt to accept the energy specified to store 
        and reject shortly after, reducing as necessary due to efficiency loss.

        Returns the energy accepted.
        """
        pass
    
    @abstractmethod
    def get_energy(self, des_energy_wh) -> float:
        """
        Attempt to provide the energy specified either from a storage device or grid.
        Actual energy depleted may be greater than the returned energy
        due to efficiency loss.

        Returns the energy provided.
        """
        pass

class SolarArray(PowerDevice):
    def __init__(self, panel_num):
        self.panel_num = panel_num
        self.generated_energy_wh = 0
        self.lifetime_energy_wh = 0

    def set_solar_generated_energy_wh(self, energy_per_panel_wh:float) -> float:
        self.generated_energy_wh = energy_per_panel_wh * self.panel_num
        return self.generated_energy_wh

    def get_generated_energy_wh(self) -> float:
        """
        Return the amount of remaining energy generated (solar) for this time and clear.
        Treated as the actual event of transmitting energy.
        """
        cur_produced_wh = self.generated_energy_wh
        self.lifetime_energy_wh += cur_produced_wh
        self.generated_energy_wh = 0
        return cur_produced_wh
    
    def store_energy(self, des_energy_wh) -> float:
        """
        Attempt to accept the energy specified to store, 
        reducing as necessary due to efficiency loss.

        Returns the energy accepted.
        """
        return 0
    
    def store_energy_transient(self, des_energy_wh) -> float:
        return 0
    
    def get_energy(self, des_energy_wh) -> float:
        """
        Return up to self.generated_energy_wh, reducing available energy by des_energy_wh
        """
        energy_provided = min(des_energy_wh, self.generated_energy_wh)
        self.generated_energy_wh -= energy_provided
        self.lifetime_energy_wh += energy_provided
        return energy_provided

def is_not_strictly_increasing(lst):
    for i in range(len(lst) - 1):
        if lst[i] >= lst[i + 1]:  # Check if the current element is not less than the next
            return True  # The list is not strictly increasing
    return False  # The list is strictly increasing

class Table1D():
    def __init__(self, x_ary:float, y_ary:float):
        if len(x_ary) != len(y_ary):
            raise ValueError("x and y must have the same length")
        elif len(x_ary) == 0:
            raise ValueError("x and y arrays must not be empty")
        elif is_not_strictly_increasing(x_ary):
            raise ValueError("x array must be strictly increasing")
        self.x_ary = x_ary
        self.y_ary = y_ary
    def getValue(self, xVal):
        for i in range(len(self.x_ary) - 1):
            # Check if x lies between self.x_ary[i] and self.x_ary[i + 1]
            if self.x_ary[i] <= xVal <= self.x_ary[i + 1]:
                # Perform linear interpolation
                y = self.y_ary[i] + (xVal - self.x_ary[i]) * (self.y_ary[i + 1] - self.y_ary[i]) / (self.x_ary[i + 1] - self.x_ary[i])
                return y
        raise ValueError("x is out of range of the given x_ary")
        

class SolarBattery(PowerDevice):
    def __init__(self, usable_energy_kwh, charge_eff=0.93, discharge_eff=0.9) -> None:
        self.usable_energy_kwh = usable_energy_kwh
        self.stored_energy_kwh = usable_energy_kwh/2
        self.charge_eff = charge_eff
        self.discharge_eff = discharge_eff
        self.throughput_wh = 0
        self.max_c_rate = 5
        self.discharge_soc_degradation = Table1D(x_ary=[0,0.2,1],y_ary=[0,0.6,1])
        self._cur_ts_discharge_wh = 0
        self._cur_ts_charge_wh = 0
        self._cur_ts = None
    
    @property
    def soc(self):
        return self.stored_energy_kwh/self.usable_energy_kwh
    
    @property
    def cur_ts_discharge_wh(self):
        return self._cur_ts_discharge_wh
    @property
    def cur_ts_charge_wh(self):
        return self._cur_ts_charge_wh
    
    def reset_ts(self):
        if self._cur_ts is None or self._cur_ts != self.time_obj.sim_time:
            self._cur_ts_discharge_wh = 0
            self._cur_ts_charge_wh = 0
            self.cur_ts = self.time_obj.sim_time

    def get_generated_energy_wh(self) -> float:
        """
        Return the amount of energy generated (solar) for this time and clear.
        """
        return 0
    
    def store_energy(self, des_energy_wh) -> float:
        """
        Attempt to accept the energy specified to store, 
        reducing as necessary due to efficiency loss.

        Returns the energy accepted.
        """
        self.reset_ts()

        #TODO!!
        # Add to _cur_ts_charge_wh

    def store_energy_transient(self, des_energy_wh) -> float:
        """
        Attempt to accept the energy specified to store 
        and reject shortly after, reducing as necessary due to efficiency loss.

        Returns the energy accepted.
        """


    def get_energy(self, des_energy_wh) -> float:
        """
        Attempt to provide the energy specified either from a storage device or grid.
        Actual energy depleted may be greater than the returned energy
        due to efficiency loss.

        Returns the energy provided.
        """
        self.reset_ts()

        #TODO!!
        # Add to _cur_ts_discharge_wh
    
class Grid(PowerDevice):
    def __init__(self, initial_credits,
                 weekday_on_peak_start:time = time(15,0,0), #3:00PM
                 weekday_on_peak_end:time = time(19,0,0), #7:00PM
                 weekend_on_peak_start:time = time(15,0,0), #3:00PM
                 weekend_on_peak_end:time = time(19,0,0), #7:00PM
                 weekday_off_peak_cost_per_kwh=0.17885,
                 weekday_on_peak_cost_per_kwh=0.19374,
                 weekend_off_peak_cost_per_kwh=0.17885,
                 weekend_on_peak_cost_per_kwh=0.17885,
                 weekday_off_peak_gen_pay_per_kwh=0.08978,
                 weekday_on_peak_gen_pay_per_kwh=0.10467,
                 weekday_off_peak_creditable_per_kwh=0.17885,
                 weekday_on_peak_creditable_per_kwh=0.19374,
                 weekend_off_peak_gen_pay_per_kwh=0.08978,
                 weekend_on_peak_gen_pay_per_kwh = 0.08978,
                 weekend_off_peak_creditable_per_kwh=0.17885,
                 weekend_on_peak_creditable_per_kwh=0.17885) -> None:
        self.weekday_on_peak_start = weekday_on_peak_start
        self.weekday_on_peak_end = weekday_on_peak_end
        self.weekday_off_peak_cost_per_kwh = weekday_off_peak_cost_per_kwh
        self.weekday_on_peak_cost_per_kwh = weekday_on_peak_cost_per_kwh
        self.weekday_off_peak_gen_pay_per_kwh = weekday_off_peak_gen_pay_per_kwh
        self.weekday_on_peak_gen_pay_per_kwh = weekday_on_peak_gen_pay_per_kwh

        self.weekday_off_peak_creditable_per_kwh = weekday_off_peak_creditable_per_kwh
        self.weekday_on_peak_creditable_per_kwh = weekday_on_peak_creditable_per_kwh

        self.weekend_on_peak_start = weekend_on_peak_start
        self.weekend_on_peak_end = weekend_on_peak_end
        self.weekend_off_peak_cost_per_kwh = weekend_off_peak_cost_per_kwh
        self.weekend_on_peak_cost_per_kwh = weekend_on_peak_cost_per_kwh
        self.weekend_off_peak_gen_pay_per_kwh = weekend_off_peak_gen_pay_per_kwh
        self.weekend_on_peak_gen_pay_per_kwh = weekend_on_peak_gen_pay_per_kwh

        self.weekend_off_peak_creditable_per_kwh = weekend_off_peak_creditable_per_kwh
        self.weekend_on_peak_creditable_per_kwh = weekend_on_peak_creditable_per_kwh

        self.available_credits_dollars = initial_credits
        self.money_spent_dollars = 0

        self._cur_ts_import_wh = 0
        self._cur_ts_export_wh = 0
        self._cur_cost = 0
        self._cur_credit = 0
        self._cur_ts = None

    @property
    def cur_ts_import_wh(self):
        return self._cur_ts_import_wh
    @property
    def cur_ts_export_wh(self):
        return self._cur_ts_export_wh
    @property
    def cur_cost(self):
        return self._cur_credit
    @property
    def cur_credit(self):
        return self._cur_credit

    def reset_ts(self) -> float:
        if self._cur_ts is None or self._cur_ts != self.time_obj.sim_time:
            self._cur_ts_export_wh = 0
            self._cur_ts_import_wh = 0
            self._cur_cost = 0
            self._cur_credit = 0
            self.cur_ts = self.time_obj.sim_time

    def get_generated_energy_wh(self) -> float:
        """
        Return the amount of energy generated (solar) for this time and clear.
        """
        return 0
    
    def store_energy(self, des_energy_wh) -> float:
        """
        Attempt to accept the energy specified to store, 
        reducing as necessary due to efficiency loss.

        Returns the energy accepted.
        """
        self.reset_ts()
        if self._cur_ts is None or self._cur_ts != self.time_obj.sim_time:
            self._cur_ts_export_wh = 0
            self._cur_ts_import_wh = 0
            self.cur_ts = self.time_obj.sim_time
        #TODO: need to set _cur_ts_export and import
        #TODO!!

    def store_energy_transient(self, des_energy_wh) -> float:
        """
        Attempt to accept the energy specified to store 
        and reject shortly after, reducing as necessary due to efficiency loss.

        Returns the energy accepted.
        """


    def get_energy(self, des_energy_wh) -> float:
        """
        Attempt to provide the energy specified either from a storage device or grid.
        Actual energy depleted may be greater than the returned energy
        due to efficiency loss.

        Returns the energy provided.
        """
        self.reset_ts()
        #TODO: need to set _cur_ts_export and import

        #TODO!!

class EnergyLoad:
    def __init__(self):
        self.energy_usage_wh = 0
        self.remaining_load_wh = 0
    def add_energy_usage(self, energy_wh):
        self.energy_usage_wh += energy_wh
    def draw_energy(self, power_device_list:PowerDevice) -> None:
        for dev in power_device_list:
            self.remaining_load_wh -= dev.get_energy(self.remaining_load_wh)
            if self.remaining_load_wh == 0:
                return
            
        if self.remaining_load_wh > 0:
            raise ValueError("Not all load could be drawn with the provided power device list!")

    
class SimController:
    def __init__(self, panels:SolarArray, battery:SolarBattery, grid:Grid):
        self.solar = panels
        self.battery = battery
        self.grid = grid
        self.time = SimTime

        #Configure all components to have the same simulation time object
        self.solar.time_obj = self.time
        self.battery.time_obj = self.time
        self.grid.time_obj = self.time

    def simulate(self, energy_timeseries, timeseries_panel_num):
        # Define column names
        columns = ["timestamp", 
                   "produced_wh", "consumed_wh", "stored_wh", "exported_wh", "imported_wh", 
                   "soc", "batt_throughput_kwh", 
                   "import_cost", "credits_earned", "credits_available", "lifetime_import_cost"]

        # Create an empty DataFrame
        results_df = pd.DataFrame(columns=columns)

        load_obj = EnergyLoad()
        energy_device_list = [self.solar, self.battery, self.grid] #order matters! Preference of energy usage
        for step, step_data in enumerate(energy_timeseries):
            cur_time = step_data.timestamp_start

            transient_grid_wh = min(step_data.import_wh, step_data.export_wh)
            transient_batt_wh = min(step_data.batt_charge_wh, step_data.batt_discharge_wh)
            cur_transient_wh = transient_grid_wh + transient_batt_wh

            # Setup the time step
            self.time.sim_time = cur_time
            cur_produced_wh = self.solar.set_solar_generated_energy_wh(step_data.production_wh / timeseries_panel_num)
            load_obj.add_energy_usage(step_data.consumption_wh + step_data.batt_discharge_wh - step_data.batt_charge_wh)

            #Begin energy transfer
            load_obj.draw_energy(energy_device_list)

            extra_energy_wh = self.solar.get_generated_energy_wh()
            for dev in energy_device_list:
                extra_energy_wh -= dev.store_energy(extra_energy_wh)

            for dev in energy_device_list:
                cur_transient_wh -= dev.store_energy_transient(cur_transient_wh)

            step_data = {
                "timestamp": cur_time,
                "produced_wh": cur_produced_wh,
                "consumed_wh": step_data.consumption_wh,
                "stored_wh": self.battery.cur_ts_charge_wh - self.battery.cur_ts_discharge_wh,
                "exported_wh": self.grid.cur_ts_export_wh,
                "imported_wh": self.grid.cur_ts_import_wh,
                "soc": self.battery.soc,
                "batt_throughput_kwh": self.battery.throughput_wh,
                "import_cost": self.grid.cur_cost,
                "credits_earned": self.grid.cur_credit,
                "credits_available": self.grid.available_credits_dollars,
                "lifetime_import_cost": self.grid.money_spent_dollars,
                }
            
            results_df.append(step_data)

        return results_df