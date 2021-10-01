import matplotlib.pyplot as plt
import csv

x=[]
y=[]
p=[]
# log_2508_batTRAXAS.csv

with open('testowy.csv', 'r') as csvfile:
    plots=csv.reader(csvfile, delimiter=';')
    for row in plots:
        x.append(float(row[0]))     #current    
        y.append(float(row[1]))     #voltage
        p.append(float(row[2]))

plt.plot(x, y)
plt.plot(x, p)
plt.ylim(bottom=0)

plt.title('Voltage - Current characteristics')
plt.ylabel('Current/Power')
plt.xlabel('Voltage')
plt.grid(color='gray', linestyle='-', linewidth=1)

plt.show()