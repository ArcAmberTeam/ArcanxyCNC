library IEEE;
use IEEE.std_logic_1164.all;  -- defines std_logic types
use IEEE.STD_LOGIC_ARITH.ALL;
use IEEE.STD_LOGIC_UNSIGNED.ALL;

-- Copyright (C) 2007, Peter C. Wallace, Mesa Electronics
-- http://www.mesanet.com
--
-- This program is is licensed under a disjunctive dual license giving you
-- the choice of one of the two following sets of free software/open source
-- licensing terms:
--
--    * GNU General Public License (GPL), version 2.0 or later
--    * 3-clause BSD License
-- 
--
-- The GNU GPL License:
-- 
--     This program is free software; you can redistribute it and/or modify
--     it under the terms of the GNU General Public License as published by
--     the Free Software Foundation; either version 2 of the License, or
--     (at your option) any later version.
-- 
--     This program is distributed in the hope that it will be useful,
--     but WITHOUT ANY WARRANTY; without even the implied warranty of
--     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
--     GNU General Public License for more details.
-- 
--     You should have received a copy of the GNU General Public License
--     along with this program; if not, write to the Free Software
--     Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
-- 
-- 
-- The 3-clause BSD License:
-- 
--     Redistribution and use in source and binary forms, with or without
--     modification, are permitted provided that the following conditions
--     are met:
-- 
--   * Redistributions of source code must retain the above copyright
--     notice, this list of conditions and the following disclaimer.
-- 
--   * Redistributions in binary form must reproduce the above
--     copyright notice, this list of conditions and the following
--     disclaimer in the documentation and/or other materials
--     provided with the distribution.
-- 
--   * Neither the name of Mesa Electronics nor the names of its
--     contributors may be used to endorse or promote products
--     derived from this software without specific prior written
--     permission.
-- 
-- 
-- Disclaimer:
-- 
--     THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
--     "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
--     LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
--     FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
--     COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
--     INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
--     BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
--     LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
--     CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
--     LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
--     ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
--     POSSIBILITY OF SUCH DAMAGE.
-- 

use work.IDROMConst.all;

package PIN_Rosetta_34 is
    constant ModuleID : ModuleIDType :=( 
        (HM2DPLLTag,    x"00",  ClockLowTag,    x"01",  HM2DPLLBaseRateAddr&PadT,       HM2DPLLNumRegs,         x"00",  HM2DPLLMPBitMask),
        (WatchDogTag,   x"00",  ClockLowTag,    x"01",  WatchDogTimeAddr&PadT,          WatchDogNumRegs,        x"00",  WatchDogMPBitMask),
        (IOPortTag,     x"00",  ClockLowTag,    x"02",  PortAddr&PadT,                  IOPortNumRegs,          x"00",  IOPortMPBitMask),
        (StepGenTag,    x"02",  ClockLowTag,    x"08",  StepGenRateAddr&PadT,           StepGenNumRegs,         x"00",  StepGenMPBitMask),
        (InMTag,        x"00",  ClockLowTag,    x"01",  InMControlAddr&PadT,            InMNumRegs,             x"00",  InMMPBitMask),
        (OutMTag,       x"00",  ClockLowTag,    x"01",  OutMDataAddr&PadT,              OutMNumRegs,            x"00",  OutMMPBitMask),
        (LEDTag,        x"00",  ClockLowTag,    x"01",  LEDAddr&PadT,                   LEDNumRegs,             x"00",  LEDMPBitMask),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (NullTag,       x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000000"),
        (InMWidth0Tag,  x"00",  NullTag,        x"00",  NullAddr&PadT,                  x"00",                  x"00",  x"00000008") -- hide this tag here until we find a better way       
);
        
	constant PinDesc : PinDescType :=(    
---     Base Func & unit  & sec func    &   sec pin                 --- I/O   26 HDR  IDC DB25  Function   Dir     NET   
        IOPortTag & x"00" & StepGenTag  &   StepGenStepPin,         --- 0       1         1       Step    Out     PUL_1  
        IOPortTag & x"00" & InMTag      &   InMData0Pin,            --- 2       3         2       Limit   In      LIMIT_1
        IOPortTag & x"01" & StepGenTag  &   StepGenStepPin,         --- 4       5         3       Step    Out     PUL_2  
        IOPortTag & x"00" & InMTag      &   InMData1Pin,            --- 6       7         4       Limit   In      LIMIT_2
        IOPortTag & x"02" & StepGenTag  &   StepGenStepPin,         --- 8       9         5       Step    Out     PUL_3  
        IOPortTag & x"02" & StepGenTag  &   StepGenDirPin,          --- 9       11        6       Dir     Out     DIR_3  
        IOPortTag & x"00" & InMTag      &   InMData2Pin,            --- 10      13        7       Limit   In      LIMIT_3
        IOPortTag & x"00" & OutMTag     &   OutMData2Pin,           --- 11      15        8       ENA     Out     ENA_3  
        IOPortTag & x"03" & StepGenTag  &   StepGenStepPin,         --- 12      17        9       Step    Out     PUL_4  
        IOPortTag & x"03" & StepGenTag  &   StepGenDirPin,          --- 13      19        10      Dir     Out     DIR_4  
        IOPortTag & x"00" & InMTag      &   InMData3Pin,            --- 14      21        11      Limit   In      LIMIT_4
        IOPortTag & x"00" & OutMTag     &   OutMData3Pin,           --- 15      23        12      ENA     Out     ENA_4  
        IOPortTag & x"00" & NullTag     &   NullPin,                --- 16      25        13      xo1     out            
        IOPortTag & x"00" & StepGenTag  &   StepGenDirPin,          --- 1       2         14      Dir     Out     DIR_1  
        IOPortTag & x"00" & OutMTag     &   OutMData0Pin,           --- 3       4         15      ENA     Out     ENA_1  
        IOPortTag & x"01" & StepGenTag  &   StepGenDirPin,          --- 5       6         16      Dir     Out     DIR_2  
        IOPortTag & x"00" & OutMTag     &   OutMData1Pin,           --- 7       8         17      ENA     Out     ENA_2  
                                                                                                                        
---     Base Func & unit  & sec func    &   sec pin                 --- I/O   26 HDR  IDC DB25  Function   Dir     NET
        IOPortTag & x"04" & StepGenTag  &   StepGenStepPin,         --- 17      1         1       Step    Out     PUL_5
        IOPortTag & x"00" & InMTag      &   InMData0Pin,            --- 19      3         2       Limit   In      LIMIT_5
        IOPortTag & x"05" & StepGenTag  &   StepGenStepPin,         --- 21      5         3       Step    Out     PUL_6
        IOPortTag & x"00" & InMTag      &   InMData1Pin,            --- 23      7         4       Limit   In      LIMIT_6
        IOPortTag & x"06" & StepGenTag  &   StepGenStepPin,         --- 25      9         5       Step    Out     PUL_7
        IOPortTag & x"06" & StepGenTag  &   StepGenDirPin,          --- 26      11        6       Dir     Out     DIR_7
        IOPortTag & x"00" & InMTag      &   InMData2Pin,            --- 27      13        7       Limit   In      LIMIT_7
        IOPortTag & x"00" & OutMTag     &   OutMData2Pin,           --- 28      15        8       ENA     Out     ENA_7
        IOPortTag & x"07" & StepGenTag  &   StepGenStepPin,         --- 29      17        9       Step    Out     PUL_8
        IOPortTag & x"07" & StepGenTag  &   StepGenDirPin,          --- 30      19        10      Dir     Out     DIR_8
        IOPortTag & x"00" & InMTag      &   InMData3Pin,            --- 31      21        11      Limit   In      LIMIT_8
        IOPortTag & x"00" & OutMTag     &   OutMData3Pin,           --- 32      23        12      ENA     Out     ENA_8
        IOPortTag & x"00" & NullTag     &   NullPin,                --- 33      25        13      xo1     out     
        IOPortTag & x"04" & StepGenTag  &   StepGenDirPin,          --- 18      2         14      Dir     Out     DIR_5
        IOPortTag & x"00" & OutMTag     &   OutMData0Pin,           --- 20      4         15      ENA     Out     ENA_5
        IOPortTag & x"05" & StepGenTag  &   StepGenDirPin,          --- 22      6         16      Dir     Out     DIR_6
        IOPortTag & x"00" & OutMTag     &   OutMData1Pin,           --- 24      8         17      ENA     Out     ENA_6


        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin, -- added for 34 pin 5I25
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,


        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin, -- added for IDROM v3
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
                    
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,
        emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin,emptypin);

end package PIN_Rosetta_34;
