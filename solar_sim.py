from abc import ABC, abstractmethod
from datetime import time, datetime

"""
TODO: This simulation needs to run with the system as is, then compare to 
the system modified as requested.
Return aggregate values, but also timeseries... (database?)
"""

class Sim_time:
    def __init__(self) -> None:
        self.time = datetime(0,0,0)

class Power_device(ABC):
    def __init__(self, time_obj) -> None:
        self.time_obj = time_obj
    @abstractmethod
    def get_generated_energy(self) -> float:
        """
        Return the amount of energy generated (solar) for this time and clear.
        """
        pass

    @abstractmethod
    def store_energy(self, des_energy_kwh) -> float:
        """
        Attempt to accept the energy specified to store, 
        reducing as necessary due to efficiency loss.

        Returns the energy accepted.
        """
        pass
    
    @abstractmethod
    def get_energy(self, des_energy_kwh) -> float:
        """
        Attempt to provide the energy specified either from a storage device or grid.
        Actual energy depleted may be greater than the returned energy
        due to efficiency loss.

        Returns the energy provided.
        """
        pass

class Solar_array(Power_device):
    def __init__(self, time_obj, panel_num):
        super().__init__(time_obj)
        self.panel_num = panel_num
        self.generated_energy_kwh = 0

    def get_generated_energy(self) -> float:
        """
        Return the amount of energy generated (solar) for this time and clear.
        """
        self.generated_energy_kwh = 0
        return self.generated_energy_kwh
    
    def store_energy(self, des_energy_kwh) -> float:
        """
        Attempt to accept the energy specified to store, 
        reducing as necessary due to efficiency loss.

        Returns the energy accepted.
        """
        return 0
    
    def get_energy(self, des_energy_kwh) -> float:
        """
        Not applicable for solar array!!
        """
        return 0

class Solar_battery(Power_device):
    def __init__(self, time_obj, usable_energy_kwh, charge_eff=0.93, discharge_eff=0.9) -> None:
        super().__init__(time_obj)
        self.usable_energy_kwh = usable_energy_kwh
        self.stored_energy_kwh = usable_energy_kwh/2
        self.charge_eff = charge_eff
        self.discharge_eff = discharge_eff
        self.throughput_kwh = 0
    
    @property
    def soc(self):
        return self.stored_energy_kwh/self.usable_energy_kwh
    
    def get_generated_energy(self) -> float:
        """
        Return the amount of energy generated (solar) for this time and clear.
        """
        return 0
    
    def store_energy(self, des_energy_kwh) -> float:
        """
        Attempt to accept the energy specified to store, 
        reducing as necessary due to efficiency loss.

        Returns the energy accepted.
        """
        #TODO!!

    def get_energy(self, des_energy_kwh) -> float:
        """
        Attempt to provide the energy specified either from a storage device or grid.
        Actual energy depleted may be greater than the returned energy
        due to efficiency loss.

        Returns the energy provided.
        """
        #TODO!!
    
class Grid(Power_device):
    def __init__(self, time_obj, initial_credits) -> None:
        super().__init__(time_obj)
        self.weekday_on_peak_start = time(15,0,0) #3:00pm
        self.weekday_on_peak_end = time(19,0,0) #7:00pm
        self.weekday_off_peak_cost_per_kwh
        self.weekday_on_peak_cost_per_kwh
        self.weekday_off_peak_gen_pay_per_kwh
        self.weekday_on_peak_gen_pay_per_kwh

        self.weekday_off_peak_creditable_per_kwh
        self.weekday_on_peak_creditable_per_kwh

        self.weekend_on_peak_start = time(15,0,0) #3:00pm
        self.weekend_on_peak_end = time(19,0,0) #7:00pm
        self.weekend_off_peak_cost_per_kwh
        self.weekend_on_peak_cost_per_kwh
        self.weekend_off_peak_gen_pay_per_kwh
        self.weekend_on_peak_gen_pay_per_kwh

        self.weekend_off_peak_creditable_per_kwh
        self.weekend_on_peak_creditable_per_kwh

        self.available_credits_dollars = initial_credits
        self.money_spent_dollars = 0

    def get_generated_energy(self) -> float:
        """
        Return the amount of energy generated (solar) for this time and clear.
        """
        return 0
    
    def store_energy(self, des_energy_kwh) -> float:
        """
        Attempt to accept the energy specified to store, 
        reducing as necessary due to efficiency loss.

        Returns the energy accepted.
        """
        #TODO!!

    def get_energy(self, des_energy_kwh) -> float:
        """
        Attempt to provide the energy specified either from a storage device or grid.
        Actual energy depleted may be greater than the returned energy
        due to efficiency loss.

        Returns the energy provided.
        """
        #TODO!!

class Energy_load:
    def __init__(self):
        self.energy_usage_kwh = 0

    