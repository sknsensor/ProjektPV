import pyvisa
import time
import csv
import matplotlib.pyplot as plt
import numpy as np
import csv
from dataclasses import dataclass
from sklearn.linear_model import LinearRegression

def linear_regression(x, y):
    x = np.array(x).reshape((-1, 1))
    y = np.array(y)
    model = LinearRegression().fit(x, y) 
    r_sq = model.score(x, y)

    return model.coef_[0]

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
        slope   : float

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

        delay = 0.1
        step = 0.001

        current_measured = 0
        #Operowanie na prądzie
        while current_measured < 0.90*short_current:
            #inst.write("SOUR:VOLT "+str(voltage_set))
            inst.write("SOUR:CURR "+str(current_set))  
            time.sleep(delay)

            power_measured = inst.query_ascii_values("MEAS:POW?")[0]
            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]

            if len(measurements) >= 25:
                r_voltage = [m.voltage for m in measurements][-25:]
                r_current = [m.current for m in measurements][-25:]
                lin_reg = linear_regression(r_voltage, r_current)
            else:
                lin_reg = 0

            measurements.append(Measurement(voltage_measured, current_measured, power_measured, 5*(lin_reg)))

            current_set += step

            print(current_set, current_measured)

        #Operacja na napięciu
        voltage_set = measurements[-1].voltage
        voltage_step = 0.04
        
        setup("voltage")
        while voltage_set > 0:
            inst.write("SOUR:VOLT "+str(voltage_set))
            time.sleep(delay)

            power_measured = inst.query_ascii_values("MEAS:POW?")[0]
            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]

            voltage_set -= voltage_step

            if len(measurements) >= 5:
                r_voltage = [m.voltage for m in measurements][-5:]
                r_current = [m.current for m in measurements][-5:]
                lin_reg = linear_regression(r_voltage, r_current)
            else:
                lin_reg = 0

            measurements.append(Measurement(voltage_measured, current_measured, power_measured, 5*(lin_reg)))
        
    elif mode=="automatic":
        setup()
        
        #Pomiar maksymalnego napięcia i prądu 
        full_voltage = int(inst.query_ascii_values("MEAS:VOLT?")[0])
        short_current = short_circuit_test()[1]
        step_current = 0.9 * short_current / 5

        time.sleep(2)

        voltage_set = full_voltage
        current_set = 0

        delay = 0.4
        # last_power = 0

        current_measured = 0

        #Operowanie na prądzie
        print("Pomiar sterowany prądem")
        while current_measured < 0.89 * short_current:
            # if voltage_set <= 0 or turns >= max_turns:
            #     break

            #inst.write("SOUR:VOLT "+str(voltage_set))
            inst.write("SOUR:CURR "+str(current_set))  
            time.sleep(delay)

            power_measured = inst.query_ascii_values("MEAS:POW?")[0]
            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]
            #power_measured = voltage_measured * current_measured


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
            
            measurements.append(Measurement(voltage_measured, current_measured, power_measured, 0))
            # r_voltage.append(voltage_measured)
            # r_current.append(current_measured)

            current_set += step_current
            # if current_set < 0: current_set = 0
            # print(current_set)

            last_power = power_measured


        #Dokładny pomiar wierzchołka
        print("Pomiar Automatyczny")
        turns = 0
        max_turns = 5
        dir = -1
        min_current = measurements[-1].current
        step_voltage = full_voltage / 10
        setup("voltage")

        r_voltage = [d.voltage for d in measurements][-5:]
        r_current = [d.current for d in measurements][-5:]

        voltage_set = measurements[-1].voltage

        # while turns < max_turns:
        while voltage_set > 0.35:
            inst.write("SOUR:VOLT "+str(voltage_set))
            time.sleep(delay)

            power_measured = inst.query_ascii_values("MEAS:POW?")[0]
            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]
            #measurements.append(Measurement(voltage_measured, current_measured, power_measured))
            r_voltage = [d.voltage for d in measurements][-5:]
            r_current = [d.current for d in measurements][-5:]
            measurements.append(Measurement(voltage_measured, current_measured, power_measured, 100*linear_regression(r_voltage, r_current)))

            # r_voltage.append(voltage_measured)
            # r_current.append(current_measured)

            # if len(r_voltage) > 5:
            #     r_voltage.pop(0)
            #     r_current.pop(0)

            #slope.append(linear_regression(r_voltage, r_current))
            #print(slope)
            # if slope > 0 and dir == -1:
            #     dir = 1
            #     step /= 2
            #     if step < 0.001: step = 0.001
            #     turns += 1
            #     print("Podzial -1")
            # elif slope <= 0 and dir == 1:
            #     dir = -1
            #     step /= 2
            #     if step < 0.001: step = 0.001
            #     turns += 1
            #     print("Podzial +1")

            voltage_set += dir*step_voltage
            last_power = power_measured
            last_current = current_measured


        #Operacja na napięciu
        print("Pomiar sterowany napięciem")
        voltage_set = measurements[-1].voltage
        
        # time.sleep(2)
        while voltage_set > 0:
            inst.write("SOUR:VOLT "+str(voltage_set))
            time.sleep(delay)

            power_measured = inst.query_ascii_values("MEAS:POW?")[0]
            voltage_measured = inst.query_ascii_values("MEAS:VOLT?")[0]
            current_measured = inst.query_ascii_values("MEAS:CURR?")[0]

            voltage_set -= 0.1

            measurements.append(Measurement(voltage_measured, current_measured, power_measured, 0))

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
            csvfile.writerow((d.voltage, d.current, d.power, d.slope))

    plotter("testowy.csv")

def plotter(file):
    x=[]
    y=[]
    p=[]
    s=[]
    # log_2508_batTRAXAS.csv

    with open(file, 'r') as csvfile:
        plots=csv.reader(csvfile, delimiter=';')
        for row in plots:
            x.append(float(row[0]))     #Current    
            y.append(float(row[1]))     #Voltage
            p.append(float(row[2]))     #Power
            s.append(float(row[3]))

    plt.plot(x, y, marker='o', markersize=5, label='Current')
    plt.plot(x, p, marker='o', markersize=5, label='Power')
    plt.plot(x, s, marker='o', markersize=5, label='Slope')
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
    measure("full")
    #print(linear_regresion([6, 16, 26, 36, 46, 56], [4, 23, 10, 12, 22, 35]))
    #print(short_circuit_test())
