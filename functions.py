from numpy.core.numeric import full, zeros_like
import pyvisa
import time
import csv
import matplotlib.pyplot as plt
import numpy as np
import math
from math import sqrt, copysign
import csv
from dataclasses import dataclass

def setup(type="current"):
    global rm
    global inst
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource('ASRL4::INSTR')

    inst.write("SYST:REM")          #ustawienie obciążenia w remote mode
    inst.write("*RST")              # !!!!! zeby dialal tryb CW trzeba zakomentowac i przelaczyc obciazenie w tryb CW
    inst.write("SOUR:CURR:RANGE 30")
    inst.write("SOUR:CURR:SLEW 30")
    inst.write("SOUR:VOLT:RANGE 30")
    if type == "current":
        inst.write("SOUR:MODE CURR")
        #inst.write("SOUR:CURR 0")       #ustawienie wartości prądu
    elif type == "voltage":
        inst.write("SOUR:MODE VOLT")
        full_voltage = inst.query_ascii_values("MEAS:VOLT?")
        inst.write("SOUR:VOLT " + str(full_voltage)) 
    inst.write("SOUR:INP 1")        #komenda załącz'1'/wyłącz'0' input obciążenia

def short_circuit_test(delay=0.75):
    setup()

    inst.write("SOUR:INP:SHOR 1")      #komenda short-circuit

    time.sleep(delay)

    voltage_short = inst.query_ascii_values("MEAS:VOLT?")[0]     #pomiar napięcia
    current_short = inst.query_ascii_values("MEAS:CURR?")[0]     #pomiar prądu
    power_short = inst.query_ascii_values("MEAS:POW?")[0]        #pomiar mocy

    print("short_voltage "+str(voltage_short)+ "   short_current "+str(current_short))

    # min_volt, max_curr = 10000, 0
    # for i in range(n):
    #     voltage_short = inst.query_ascii_values("MEAS:VOLT?")[0]     #pomiar napięcia
    #     current_short = inst.query_ascii_values("MEAS:CURR?")[0]     #pomiar prądu
    #     min_volt = voltage_short if voltage_short < min_volt else min_volt
    #     max_curr = current_short if current_short > max_curr else max_curr
    #     time.sleep(0.1)

    inst.write("SOUR:INP:SHOR 0")      #komenda short-circuit

    return (voltage_short, current_short, power_short)

def getInt(message):
    min_val = 0
    max_val = 10000
    while True:
        try:
            userFloat = int(input(message))
            if not min_val <= userFloat < max_val:
                raise ValueError
            else:
                return userFloat
        except ValueError:
            print('That was not a valid numerical value, please try again')

# https://stackoverflow.com/questions/55649356/
def trenddetector(list_of_index, array_of_data, order=1):
    result = np.polyfit(list_of_index, list(array_of_data), order)
    slope = result[-2]
    return float(slope)

def stop():
    inst.write("INP 0")
    inst.write("SYST:LOC")
    inst.close()

def measure(mode="voltage", measure_range=100, step=1):
    #1.Pobieram date i czas -> tworzymy nazwę pliku 
    #2. Funkcja do zapisu do CSV

    @dataclass
    class Measurement:
        voltage : float 
        current : float
        power   : float

    measurements = []

    if mode=="current":
        setup("current")
        short_current = int(1000*short_circuit_test()[1])

        for x in range(0, short_current, step) :                            #range(początek, koniec, krok)     4000/1000 = 4A -> (x/1000.0)
            inst.write("SOUR:CURR "+str(x/1000.0))                          #ustawienie wartości prądu
            v = inst.query_ascii_values("MEAS:VOLT?")[0]
            i = inst.query_ascii_values("MEAS:CURR?")[0]
            p = inst.query_ascii_values("MEAS:POW?")[0]

            measurements.append(Measurement(v, i, p))

            print(inst.query_ascii_values("MEAS:POW?")[0])

    elif mode=="voltage":
        setup("voltage")
        full_voltage = int(inst.query_ascii_values("MEAS:VOLT?")[0]*1000) # mV
        print(full_voltage)
        
        step = -50
        for i in range(full_voltage, 0, step):
            inst.write("SOUR:VOLT "+str(i/1000))
            time.sleep(0.1)
            v = inst.query_ascii_values("MEAS:VOLT?")[0]
            i = inst.query_ascii_values("MEAS:CURR?")[0]
            p = inst.query_ascii_values("MEAS:POW?")[0]

            measurements.append(Measurement(v, i, p))


    elif mode =="full":
        delay = 0.35
        step = 0.05

        setup()
      
        #Pomiar maksymalnego napięcia i prądu 
        full_voltage = int(inst.query_ascii_values("MEAS:VOLT?")[0])
        short_voltage, short_current, short_power = short_circuit_test()
        measurements.append(Measurement(short_voltage, short_current, short_power))

        time.sleep(delay)

        voltage_set = full_voltage
        current_set = 0

        current_measured = 0
        #Operowanie na prądzie
        while current_measured < 0.90*short_current:
            #inst.write("SOUR:VOLT "+str(voltage_set))
            inst.write("SOUR:CURR "+str(current_set))  
            time.sleep(delay)

            power_measured = inst.query_ascii_values("MEAS:POW?")[0]
            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]

            measurements.append(Measurement(voltage_measured, current_measured, power_measured))

            current_set += step

            print(current_set, current_measured)


        #Operacja na napięciu
        voltage_set = measurements[-1].voltage
        #voltage_set = 4
        setup("voltage")
        inst.write("SOUR:VOLT "+str(voltage_set))
        time.sleep(delay)
        while voltage_set > 0:
            inst.write("SOUR:VOLT "+str(voltage_set))
            time.sleep(delay)

            power_measured = inst.query_ascii_values("MEAS:POW?")[0]
            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]

            voltage_set -= 0.1

            measurements.append(Measurement(voltage_measured, current_measured, power_measured))
        
    elif mode=="automatic":
        start = time.time()

        setup()
        points = 0
        
        #Pomiar maksymalnego napięcia i prądu
        full_voltage = int(inst.query_ascii_values("MEAS:VOLT?")[0])
        short_voltage, short_current, short_power = short_circuit_test()
        measurements.append(Measurement(short_voltage, short_current, short_power))

        step_voltage = full_voltage / 25 # What are you doin' step voltage? ^^
        step_current = short_current / 20

        # time.sleep(0.0001)

        #Pomiar poprzez sterowanie prądem
        current_set = 0

        delay = 0.4

        turns = 0
        max_turns = 15

        #Operowanie na prądzie
        while turns < max_turns:

            inst.write("SOUR:CURR "+str(current_set))  
            time.sleep(delay)

            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]
            power_measured = inst.query_ascii_values("MEAS:POW?")[0]
            
            measurements.append(Measurement(voltage_measured, current_measured, power_measured))
            points += 1

            # if points >= 2:
            #     try:
            #         gradient = (measurements[-1].power - measurements[-2].power)/(measurements[-1].voltage - measurements[-2].voltage)
            #     except ZeroDivisionError:
            #         pass
            #     if points == 2:
            #         initial_gradient = gradient # Oblicz pierwszy gradient
            #         step_const = step_current   # Zapamiętaj początkowy krok
            #     step_current = step_const*(gradient / initial_gradient) if step_current > 0.001 else 0.001 # Oblicz nowy krok
            #     # print(step_current)


            print('I: ', end='')
            print(current_set, current_measured)
            current_set += step_current

            if current_measured > 0.5 * short_current: break

        #Operacja na napięciu
        voltage_set = measurements[-2].voltage
        measurements.pop()
        measurements.pop()
        setup("voltage")
        inst.write("SOUR:VOLT "+str(voltage_set))
        time.sleep(0.5)

        step_const = step_voltage   # Zapamiętaj początkowy krok dla napięcia
        points_for_v = 0
        while voltage_set > 0:
            inst.write("SOUR:VOLT "+str(voltage_set))
            time.sleep(delay)

            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]
            power_measured = inst.query_ascii_values("MEAS:POW?")[0]

            measurements.append(Measurement(voltage_measured, current_measured, power_measured))
            points += 1

            # try:
            #     gradient = (measurements[-1].power - measurements[-2].power)/(measurements[-1].voltage - measurements[-2].voltage)
            # except ZeroDivisionError:
            #     pass

            # step_voltage += 0.05 * gradient
            # if step_voltage <= 0.05:  step_voltage = 0.05

            #if step_voltage > full_voltage / 25: step_voltage = full_voltage / 25

            if points_for_v >= 2:
                try:
                    gradient = (measurements[-1].power - measurements[-2].power)/(measurements[-1].voltage - measurements[-2].voltage)
                except ZeroDivisionError:
                    pass
                if points_for_v == 2:
                    initial_gradient = gradient # Oblicz pierwszy gradient
                    step_const = step_voltage   # Zapamiętaj początkowy krok
                #step_voltage = step_const*(gradient / initial_gradient) if step_voltage > 0.001 else 0.001 # Oblicz nowy krok
                step_voltage += step_voltage*copysign((abs(gradient) ** 0.1), gradient)*0.2 if step_voltage > 0.01 else 0.01
                print("gradient", gradient)

            points_for_v += 1

            # if step_voltage < 0.05: step_voltage=0.05

            print('V: ', end='')
            print(voltage_set, voltage_measured)
            voltage_set -= step_voltage


        # inst.write("SOUR:VOLT 0")
        # time.sleep(delay)

        # voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
        # current_measured = inst.query_ascii_values("MEAS:CURR?")[0]
        # power_measured = inst.query_ascii_values("MEAS:POW?")[0]

        measurements.append(Measurement(voltage_measured, current_measured, power_measured))
        points += 1
    stop()

    print("Punkty pomiarowe:", points)
    measurement_duration = time.time() - start
    print('Czas pomiaru:', measurement_duration, 's')

    save_to_csv(measurements)
    return measurements


def save_to_csv(data):
    fullname = "testowy.csv" 
    with open(fullname,"w",newline="") as csvfile:
        csvfile = csv.writer(csvfile, delimiter=';')
        #logfile.writerow(["Time", "Current requested","Current readback", "Voltage readback"])
        #logfile.writerow(fields)
        #logfile.writerow(["Time", "Current requested","Current readback", "Voltage readback"])
        newdata = sorted(data, key=lambda x: x.voltage)
        # newdata = data
        for d in newdata:
            # print((d.voltage, d.current, d.power))
            csvfile.writerow((d.voltage, d.current, d.power))

    plotter("testowy.csv")

def plotter(file):
    x=[]
    y=[]
    p=[]
    # log_2508_batTRAXAS.csv

    with open(file, 'r') as csvfile:
        plots=csv.reader(csvfile, delimiter=';')
        for row in plots:
            x.append(float(row[0]))     #current    
            y.append(float(row[1]))     #voltage
            p.append(float(row[2]))

    plt.plot(x, y, marker='o', markersize=5, label='Current')
    plt.plot(x, p, marker='o', markersize=5, label='Power')
    plt.ylim(bottom=0)

    plt.title('Voltage - Current characteristics')
    plt.legend()
    plt.ylabel('Current/Power')
    plt.xlabel('Voltage')
    plt.grid(color='gray', linestyle='-', linewidth=1)

    plt.savefig('last.png')
    plt.show()
    return 0

if __name__ == '__main__':
    #print(short_circuit_test())
    measure("automatic")