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

-- Reconstructed from the supplied GPIO table; not recovered vendor HDL.
package PIN_ZHULONG_V2_34 is
    constant ModuleID : ModuleIDType := (
        0 => (HM2DPLLTag, x"00", ClockLowTag, x"01", HM2DPLLBaseRateAddr&PadT, HM2DPLLNumRegs, x"00", HM2DPLLMPBitMask),
        1 => (WatchDogTag, x"00", ClockLowTag, x"01", WatchDogTimeAddr&PadT, WatchDogNumRegs, x"00", WatchDogMPBitMask),
        2 => (IOPortTag, x"00", ClockLowTag, x"02", PortAddr&PadT, IOPortNumRegs, x"00", IOPortMPBitMask),
        3 => (QCountTag, x"02", ClockLowTag, x"03", QCounterAddr&PadT, QCounterNumRegs, x"00", QCounterMPBitMask),
        4 => (PWMTag, x"00", ClockHighTag, x"01", PWMValAddr&PadT, PWMNumRegs, x"00", PWMMPBitMask),
        5 => (SSerialTag, x"00", ClockLowTag, x"01", SSerialCommandAddr&PadT, SSerialNumRegs, x"10", SSerialMPBitMask),
        6 => (StepGenTag, x"02", ClockLowTag, x"06", StepGenRateAddr&PadT, StepGenNumRegs, x"00", StepGenMPBitMask),
        7 => (LEDTag, x"00", ClockLowTag, x"01", LEDAddr&PadT, LEDNumRegs, x"00", LEDMPBitMask),
        others => (NullTag, x"00", NullTag, x"00", NullAddr&PadT, x"00", x"00", x"00000000")
    );
    constant PinDesc : PinDescType := (
        0 => IOPortTag & x"00" & SSerialTag & SSerialRX0Pin,
        1 => IOPortTag & x"00" & SSerialTag & SSerialTX0Pin,
        2 => IOPortTag & x"00" & SSerialTag & SSerialRX1Pin,
        3 => IOPortTag & x"00" & SSerialTag & SSerialTX1Pin,
        4 => IOPortTag & x"00" & StepGenTag & StepGenStepPin,
        5 => IOPortTag & x"00" & StepGenTag & StepGenDirPin,
        6 => IOPortTag & x"01" & StepGenTag & StepGenStepPin,
        7 => IOPortTag & x"01" & StepGenTag & StepGenDirPin,
        8 => IOPortTag & x"02" & StepGenTag & StepGenStepPin,
        9 => IOPortTag & x"02" & StepGenTag & StepGenDirPin,
        10 => IOPortTag & x"03" & StepGenTag & StepGenStepPin,
        11 => IOPortTag & x"03" & StepGenTag & StepGenDirPin,
        12 => IOPortTag & x"04" & StepGenTag & StepGenStepPin,
        13 => IOPortTag & x"04" & StepGenTag & StepGenDirPin,
        14 => IOPortTag & x"05" & StepGenTag & StepGenStepPin,
        15 => IOPortTag & x"05" & StepGenTag & StepGenDirPin,
        16 => IOPortTag & x"00" & PWMTag & PWMAOutPin,
        17 => IOPortTag & x"00" & NullTag & x"00",
        18 => IOPortTag & x"00" & NullTag & x"00",
        19 => IOPortTag & x"00" & NullTag & x"00",
        20 => IOPortTag & x"00" & NullTag & x"00",
        21 => IOPortTag & x"00" & NullTag & x"00",
        22 => IOPortTag & x"00" & NullTag & x"00",
        23 => IOPortTag & x"00" & NullTag & x"00",
        24 => IOPortTag & x"00" & NullTag & x"00",
        25 => IOPortTag & x"00" & QCountTag & QCountQAPin,
        26 => IOPortTag & x"00" & QCountTag & QCountQBPin,
        27 => IOPortTag & x"00" & QCountTag & QCountIDXPin,
        28 => IOPortTag & x"01" & QCountTag & QCountQAPin,
        29 => IOPortTag & x"01" & QCountTag & QCountQBPin,
        30 => IOPortTag & x"01" & QCountTag & QCountIDXPin,
        31 => IOPortTag & x"02" & QCountTag & QCountQAPin,
        32 => IOPortTag & x"02" & QCountTag & QCountQBPin,
        33 => IOPortTag & x"02" & QCountTag & QCountIDXPin,
        others => emptypin
    );
end package PIN_ZHULONG_V2_34;
