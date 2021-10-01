import pyvisa
import time
import csv
import matplotlib.pyplot as plt
import numpy as np
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

def short_circuit_test(t=3):
    setup()
    # while inst.query_ascii_values("MEAS:VOLT?")[0] < 8.5:
    #     time.sleep(0.1)

    inst.write("SOUR:INP:SHOR 1")      #komenda short-circuit
    min_volt, max_curr = 10000, 0

    for i in range(25):
        voltage_short = inst.query_ascii_values("MEAS:VOLT?")[0]     #pomiar napięcia
        current_short = inst.query_ascii_values("MEAS:CURR?")[0]     #pomiar prądu
        min_volt = voltage_short if voltage_short < min_volt else min_volt
        max_curr = current_short if current_short > max_curr else max_curr
        time.sleep(0.1)
    inst.write("SOUR:INP:SHOR 0")      #komenda short-circuit

    print("short_voltage "+str(voltage_short)+ "   short_current "+str(current_short))
    print("short_voltage "+str(min_volt)+ "   short_current "+str(max_curr))
    
    return (voltage_short, current_short)

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
        setup()
        
        #Pomiar maksymalnego napięcia i prądu 
        full_voltage = int(inst.query_ascii_values("MEAS:VOLT?")[0])
        short_current = short_circuit_test()[1]
        time.sleep(2)

        voltage_set = full_voltage
        current_set = 0

        delay = 0.4
        step = 0.05

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
        time.sleep(2)
        while voltage_set > 0:
            inst.write("SOUR:VOLT "+str(voltage_set))
            time.sleep(delay)

            power_measured = inst.query_ascii_values("MEAS:POW?")[0]
            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]

            voltage_set -= 0.1

            measurements.append(Measurement(voltage_measured, current_measured, power_measured))
        
    elif mode=="automatic":
        setup()
        
        #Pomiar maksymalnego napięcia i prądu 
        full_voltage = int(inst.query_ascii_values("MEAS:VOLT?")[0])
        short_current = short_circuit_test()[1]

        step_current = (0.9*short_current/5)

        time.sleep(2)

        #Pomia poprzez sterowane prądem

        voltage_set = full_voltage
        current_set = 0

        delay = 0.1
        last_power = 0
        turns = 0

        max_turns = 15
        dir = 1
        step = 0.005

        #Operowanie na prądzie
        while turns < max_turns:
            # if voltage_set <= 0 or turns >= max_turns:
            #     break

            #inst.write("SOUR:VOLT "+str(voltage_set))
            inst.write("SOUR:CURR "+str(current_set))  
            time.sleep(delay)

            power_measured = inst.query_ascii_values("MEAS:POW?")[0]
            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]


            # if current_set >= short_current:
            #     break
            #     print(short_current)
            #     break

            # if power_measured < last_power:
            #     dir = -dir
            #     step /= 2
            #     if step < 0.001: step = 0.001
            #     turns += 1

            # if not power_measured in power:
            #     power.append(power_measured)

            # if not voltage_measured in voltage:
            #     voltage.append(voltage_measured)

            # if not current_measured in current:
            #     current.append(current_measured)
            # eps = 0.1
            # voltages = [m.voltage for m in measurements]
            # voltages = np.asarray(voltages)
            # if len(voltages) > 0:
            #     idx = (np.abs(voltages - voltage_measured)).argmin()
            #     print(voltages[idx])
            # if len(voltages) > 0 and abs(voltage_measured - voltages[idx]) > eps:
            #     measurements.append(Measurement(voltage_measured, current_measured, power_measured))
            
            measurements.append(Measurement(voltage_measured, current_measured, power_measured))

            current_set += dir*step
            # if current_set < 0: current_set = 0
            # print(current_set)

            print(current_set, current_measured)

            if current_measured > 0.505: break

            last_power = power_measured

        #Operacja na napięciu
        voltage_set = measurements[-1].voltage
        #voltage_set = 4
        setup("voltage")
        while voltage_set > 0:
            inst.write("SOUR:VOLT "+str(voltage_set))
            time.sleep(delay)

            power_measured = inst.query_ascii_values("MEAS:POW?")[0]
            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]

            voltage_set -= 0.02

            measurements.append(Measurement(voltage_measured, current_measured, power_measured))


    stop()
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

    plt.show()
    return 0


if __name__ == '__main__':
    #print(short_circuit_test())
    start = time.time()
    measure("full")
    end = time.time()
    print('##########################')
    print(end - start)
