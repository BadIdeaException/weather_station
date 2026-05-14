This is the monorepo for my custom weather station. 

# Schematics

```
+--------+                                              +--------------+
| out-   |                     +--------+               |              |
| side   |<--- 433.92 MHz ---> | CC1101 | <- SPI,GDO -> |              |                +----------------+
| sensor |                     +--------+               |              |                |                |
+--------+                                              | Raspberry Pi | <---  SPI ---> | ePaper display |
                                                        | Zero 2W      |                |                |
                                                        |              |                +----------------+
+--------+                                              |              |
| BME280 | <------------------  I2C ------------------> |              |
+--------+                                              +--------------+
```
