
import pytest
import time
import sys
import csv
from SpannerTestboard import SpannerTestboard
from ut61e_py.UT61E import UT61E

testboard = SpannerTestboard("batteryTestboard")
testboard_dmm = SpannerTestboard("dmmTestboard")
DMM = UT61E(testboard_dmm)
INA219 = SpannerTestboard.INA219


CHARGER_RELAY_PIN = "D2"
LOAD_RELAY_PIN = "D6"

GREEN_LED_PIN = "A3"
RED_LED_PIN = "A4"

TEMP_PIN = "A0"
DIVIDER_PIN = "A2"
DMM_PIN = "A1"

# Voltage divider resistors
VDIV_R1 = 985000    # 985 KΩhm
VDIV_R2 = 66000     # 66 ΚΩhm

# INA219 Resistor
INA219_SHUNT_RESISTOR = 0.02


"""
 These functions are used to initiate the setup of this test file (module scoped)
 More importantly they turn off the relays after the test execution is terminated
 as a safety measure.
"""
def setup_module(module):
    """ setup any state specific to the execution of the given module."""
    testboard.digitalWrite(CHARGER_RELAY_PIN, 'LOW')
    testboard.digitalWrite(LOAD_RELAY_PIN, 'LOW')
    # Turn off the test LED indicators
    testboard.digitalWrite(GREEN_LED_PIN, 'LOW')
    testboard.digitalWrite(RED_LED_PIN, 'LOW')
    # Calibrate the INA219 module
    testboard.ina219_setGainOne()

def teardown_module(module):
    """ teardown any state that was previously setup with a setup_module method. """
    testboard.digitalWrite(CHARGER_RELAY_PIN, 'LOW')
    testboard.digitalWrite(LOAD_RELAY_PIN, 'LOW')


def tb_dag(value):
    """ Digital to analog converter for our testboard """
    return (3.3 * value) / 4096


def get_temperature(tmp_pin):
    """ Returns the temperature from the sensor pin """
    value = testboard.analogRead(tmp_pin)
    print("%f int" % value)
    voltage = tb_dag(value)
    return (voltage - 0.5) * 100


def get_voltage(voltage_pin):
    """ Returns the source voltage, from the voltage divider """

    # With voltage divider
    # value = testboard.analogRead(voltage_pin)
    # divider_voltage = tb_dag(value)
    # print("Divider voltage: " + str(divider_voltage))
    # return divider_voltage * (VDIV_R1 + VDIV_R2) / VDIV_R2

    # With DMM
    meas = DMM.get_meas()
    assert meas["data_valid"]
    assert meas["mode"] == "V/mV"
    assert meas["dc"]
    assert meas["hold"] == False
    assert meas["norm_units"] == "V"


    return meas['norm_val']


def ina219_value(meas_type):
    """ Returns Shunt Voltage MV, Current mA from the INA219 module """
    if meas_type == INA219.SHUNT_VOLTAGE_MV:
        return testboard.ina219_getValue(INA219.SHUNT_VOLTAGE_MV)
    if meas_type == INA219.CURRENT_MA:
        return testboard.ina219_getValue(INA219.SHUNT_VOLTAGE_MV) / INA219_SHUNT_RESISTOR
    return None


def seconds_passed(oldepoch, seconds):
    """ Returns true if seconds time has elapsed """
    return time.time() - oldepoch >= seconds


def test_charging_stage():

    print("----> Charging test")

    # TODO: led indicator on error
    voltage = get_voltage(DIVIDER_PIN)

    assert voltage < 41.5, "Battery already charged"

    # Turn on charging circuit
    testboard.digitalWrite(CHARGER_RELAY_PIN, 'HIGH')

    while True:
        # Read current value
        current = ina219_value(INA219.CURRENT_MA)
        print("I1 current %.3f mA" % current)
        if current < 200:
            break
        # sleep for 1 minute
        time.sleep(60)

    # Turn off charging circuit
    testboard.digitalWrite(CHARGER_RELAY_PIN, 'LOW')


def test_balancing_stage():

    print("----> Balancing test")

    start_time = time.time()

    while not seconds_passed(start_time, 3 * 3600):
        # Read voltage value
        voltage = get_voltage(DIVIDER_PIN)
        print("V2 voltage %.3f V" % voltage)

        if voltage <= 41.5:
            print("Balancing completed")
            return

        time.sleep(60)

    #TODO: led indicator
    voltage = get_voltage(DIVIDER_PIN)
    assert False, "3 hours timeout, something went wrong with bms, Voltage %.3f V" % voltage



def test_discharging_stage():

    print("----> Discharging test")

    # Turn on load
    testboard.digitalWrite(LOAD_RELAY_PIN, 'HIGH')

    values = []

    voltage = get_voltage(DIVIDER_PIN)
    while voltage >= 29:
        print("V3 voltage %.3f V" % voltage)

        # New measurement row
        values.append([
            time.time(),                                # Timestamp
            voltage,                                    # Voltage V
            ina219_value(INA219.CURRENT_MA),            # Current mA
            get_temperature(TEMP_PIN)                   # Temperature C
        ])

        # Wait for 1 minute
        time.sleep(60)
        voltage = get_voltage(DIVIDER_PIN)


    testboard.digitalWrite(LOAD_RELAY_PIN, 'LOW')

    # Print measurements as a csv file
    print("====================== CSV contents ======================")
    writer = csv.writer(sys.stdout)
    writer.writerows(values)
