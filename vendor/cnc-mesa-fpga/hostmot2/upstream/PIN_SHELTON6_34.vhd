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

package PIN_SHELTON6_34 is
	constant ModuleID : ModuleIDType :=( 
		(HM2DPLLTag,	x"00",	ClockLowTag,	x"01",	HM2DPLLBaseRateAddr&PadT,	HM2DPLLNumRegs,		x"00",	HM2DPLLMPBitMask),
		(WatchDogTag,	x"00",	ClockLowTag,	x"01",	WatchDogTimeAddr&PadT,		WatchDogNumRegs,		x"00",	WatchDogMPBitMask),
		(IOPortTag,		x"00",	ClockLowTag,	x"02",	PortAddr&PadT,					IOPortNumRegs,			x"00",	IOPortMPBitMask),
		(InMTag,			x"00",	ClockLowTag,	x"01",	InMControlAddr&PadT,			InMNumRegs,				x"00",	InMMPBitMask),
		(InMuxTag,		x"00",	ClockLowTag,	x"01",	InMuxControlAddr&PadT,		InMuxNumRegs,			x"00",	InmuxMPBitMask),
		(OutMTag,		x"00",	ClockLowTag,	x"01",	OutMDataAddr&PadT,			OutMNumRegs,			x"00",	OutMMPBitMask),
		(StepGenTag,	x"02",	ClockLowTag,	x"06",	StepGenRateAddr&PadT,		StepGenNumRegs,		x"00",	StepGenMPBitMask),
		(PWMTag,			x"00",	ClockHighTag,	x"01",	PWMValAddr&PadT,				PWMNumRegs,				x"00",	PWMMPBitMask),
		(LEDTag,			x"00",	ClockLowTag,	x"01",	LEDAddr&PadT,					LEDNumRegs,				x"00",	LEDMPBitMask),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(NullTag,		x"00",	NullTag,			x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000000"),
		(InMuxWidth0Tag,		x"00",	NullTag,	x"00",	NullAddr&PadT,					x"00",					x"00",	x"00000020"), -- hide this tag here until we find a better way
		(InMWidth0Tag,			x"00",	NullTag,	x"00",	NullAddr&PadT,					x"00",					x"00",	x"0000000C") -- hide this tag here until we find a better way
		);
		
	
	constant PinDesc : PinDescType :=(
-- 	Base func  sec unit sec func 	 sec pin					-- external DB25
		IOPortTag & x"03" & StepGenTag & StepGenDirPin,		-- I/O 00	PIN 1		Z DIR
		IOPortTag & x"03" & StepGenTag & StepGenStepPin,	-- I/O 01	PIN 14   Z STEP
		IOPortTag & x"02" & StepGenTag & StepGenDirPin,		-- I/O 02	PIN 2    Y2 DIR
		IOPortTag & x"02" & StepGenTag & StepGenStepPin,	-- I/O 03	PIN 15	Y2 STEP
		IOPortTag & x"01" & StepGenTag & StepGenDirPin,		-- I/O 04	PIN 3		Y1 DIR    
		IOPortTag & x"01" & StepGenTag & StepGenStepPin,	-- I/O 05	PIN 16   Y1 STEP
		IOPortTag & x"00" & StepGenTag & StepGenDirPin,		-- I/O 06	PIN 4		X DIR
		IOPortTag & x"00" & StepGenTag & StepGenStepPin,	-- I/O 07	PIN 17	X STEP
		IOPortTag & x"04" & StepGenTag & StepGenDirPin,		-- I/O 08	PIN 5 	A DIR
		IOPortTag & x"04" & StepGenTag & StepGenStepPin,	-- I/O 09	PIN 6		A STEP
		IOPortTag & x"05" & StepGenTag & StepGenDirPin,		-- I/O 10	PIN 7		B DIR
		IOPortTag & x"05" & StepGenTag & StepGenStepPin,	-- I/O 11	PIN 8		B STEP
		IOPortTag & x"00" & OutMTag & OutMData0Pin,   		-- I/O 12	PIN 9		RELAY 0
		IOPortTag & x"00" & OutMTag & OutMData1Pin,   		-- I/O 13	PIN 10	RELAY 1
		IOPortTag & x"00" & OutMTag & OutMData2Pin,   		-- I/O 14	PIN 11	RELAY 2
		IOPortTag & x"00" & PWMTag & PWMAOutPin,				-- I/O 15	PIN 12	SPINDLE PWM
		IOPortTag & x"00" & InMTag & InMData8Pin,       	-- I/O 16	PIN 13	PROBE IN
		
																			-- 26 HDR	-- IDC   DB25	
		IOPortTag & x"00" & InMTag & InMData3Pin,       	-- I/O 17	PIN 1		PIN 1 	Y1 LIMIT
		IOPortTag & x"00" & InMTag & InMData2Pin,       	-- I/O 18   PIN 2		PIN 14	X LIMIT
		IOPortTag & x"00" & InMTag & InMData5Pin,       	-- I/O 19   PIN 3		PIN 2	   Z LIMIT
		IOPortTag & x"00" & InMTag & InMData4Pin,       	-- I/O 20	PIN 4		PIN 15	Y2 LIMIT
		IOPortTag & x"00" & InMTag & InMData7Pin,       	-- I/O 21	PIN 5		PIN 3	   B LIMIT    
		IOPortTag & x"00" & InMTag & InMData6Pin,       	-- I/O 22	PIN 6		PIN 16	A LIMIT
		IOPortTag & x"00" & InMTag & InMData0Pin,       	-- I/O 23	PIN 7		PIN 4	   MPG A
		IOPortTag & x"00" & InMTag & InMData1Pin,       	-- I/O 24	PIN 8		PIN 17	MPG B
		IOPortTag & x"00" & InMTag & InMDataBPin,       	-- I/O 25	PIN 9		PIN 5	   ESTOP
		IOPortTag & x"00" & InMTag & InMDataAPin,       	-- I/O 26	PIN 11	PIN 6	   ATLAS
		IOPortTag & x"00" & InMTag & InMData9Pin,       	-- I/O 27	PIN 13	PIN 7	   Z PROBE
		IOPortTag & x"00" & InMuxTag & InMuxDataPin,       -- I/O 28	PIN 15	PIN 8	   MUX DATA
		IOPortTag & x"00" & InMuxTag & InMuxAddr0Pin,      -- I/O 29	PIN 17	PIN 9	   MUX A0
		IOPortTag & x"00" & InMuxTag & InMuxAddr1Pin,      -- I/O 30	PIN 19	PIN 10	MUX A1
		IOPortTag & x"00" & InMuxTag & InMuxAddr2Pin,      -- I/O 31	PIN 21	PIN 11  	MUX A2
		IOPortTag & x"00" & InMuxTag & InMuxAddr3Pin,      -- I/O 32	PIN 23	PIN 12	MUX A3
		IOPortTag & x"00" & InMuxTag & InMuxAddr4Pin,      -- I/O 33	PIN 25	PIN 13	MUX A4
		

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

end package PIN_SHELTON6_34;
