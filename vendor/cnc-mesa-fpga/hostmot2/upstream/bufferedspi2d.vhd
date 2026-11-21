library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.STD_LOGIC_ARITH.ALL;
use IEEE.STD_LOGIC_UNSIGNED.ALL;
--
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
--         * Redistributions of source code must retain the above copyright
--           notice, this list of conditions and the following disclaimer.
-- 
--         * Redistributions in binary form must reproduce the above
--           copyright notice, this list of conditions and the following
--           disclaimer in the documentation and/or other materials
--           provided with the distribution.
-- 
--         * Neither the name of Mesa Electronics nor the names of its
--           contributors may be used to endorse or promote products
--           derived from this software without specific prior written
--           permission.
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

entity bufferedspid is
    generic (
		cswidth : integer := 4;
		gatedcs : boolean := true
		);    
	port ( 
		clk : in std_logic;
		ibus : in std_logic_vector(31 downto 0);
      obus : out std_logic_vector(31 downto 0);
		addr : in std_logic_vector(3 downto 0);
		hostpush : in std_logic;
		hostpop : in std_logic;
		startautosend : in std_logic;
		loadautocontrolreg : in std_logic;
		readautocontrolreg : in std_logic;
		loaddesc : in std_logic;
		loadautodesc : in std_logic;
		loadasend : in std_logic;
		clear : in std_logic;
		readcount : in std_logic;
		timers : in std_logic_vector;
      spiclk : out std_logic;
      spiin : in std_logic;
		spiout: out std_logic;
		spiframe: out std_logic;
		spicsout: out std_logic_vector(cswidth-1 downto 0)
       );
end bufferedspid;

architecture behavioral of bufferedspid is

constant DivWidth: integer := 8;


-- spi interface related signals

signal RateDiv : std_logic_vector(DivWidth -1 downto 0);
signal ModeReg : std_logic_vector(31 downto 0);
signal LoadData : std_logic;
signal StartCycle : std_logic_vector(2 downto 0);
signal Run : std_logic;
signal FrameStart : std_logic;
alias  BitcountReg : std_logic_vector(5 downto 0) is ModeReg(5 downto 0);
alias CPOL : std_logic is ModeReg(6);
alias CPHA : std_logic is ModeReg(7);
alias RateDivReg : std_logic_vector(DivWidth -1 downto 0) is ModeReg(15 downto 8);
alias CSReg : std_logic_vector(cswidth -1 downto 0) is  ModeReg(cswidth-1 +16 downto 16);
alias CSIdleTimerReg : std_logic_vector(4 downto 0) is ModeReg(28 downto 24);
alias ByteMode : std_logic is ModeReg(29);
alias DontClearFrame : std_logic is ModeReg(30);
alias DontEcho : std_logic is ModeReg(31);
signal DontEchoReg: std_logic; 
signal BitCount : std_logic_vector(5 downto 0);
signal OldBitCount5: std_logic; 
signal ClockFF: std_logic; 
signal SPISregIn: std_logic_vector(31 downto 0);
signal SPISregOut: std_logic_vector(31 downto 0);
signal LFrame: std_logic; 
signal OldLFrame: std_logic; 
signal EFrame: std_logic;
signal Dav: std_logic; 
signal SPIData: std_logic;
signal CSIdleTimer: std_logic_vector(4 downto 0);
alias CSIdleTimerDone: std_logic is CSIdleTimer(4);
signal CSHold: std_logic;
signal CSHoldTimer: std_logic_vector(7 downto 0);
signal CSIdle: std_logic;
signal CSPrescale: integer;

-- input FIFO related signals
	signal ipopadd: std_logic_vector(4 downto 0) := "11111";
	signal ipopdata: std_logic_vector(31 downto 0);
	signal idatacounter: std_logic_vector(5 downto 0);
	signal ipush: std_logic;   
	signal ififohasdata: std_logic; 

-- output FIFO related signals
	signal opushdata: std_logic_vector(35 downto 0);
	signal opopadd: std_logic_vector(4 downto 0) := "11111";
	signal opopdata: std_logic_vector(35 downto 0);
	signal odatacounter: std_logic_vector(5 downto 0); 
	signal opop: std_logic;  
	signal ofifohasdata: std_logic; 
 
-- autosend table related signals
	
	signal autocontrolreg: std_logic_vector(15 downto 0);
	alias  autosendlength: std_logic_vector(4 downto 0) is AutoControlReg (4 downto 0);
	signal autosendaddr: std_logic_vector(4 downto 0);
	signal autosenddata: std_logic_vector(35 downto 0);
	signal autosendbusy : std_logic; 
	alias  autosendenable : std_logic is AutoControlReg(8); 
	alias  autosendcollision : std_logic is AutoControlReg(10); 
	signal autosendreq : std_logic;
	
-- DPLL related signals

	alias timerselect: std_logic_vector(2 downto 0) is Autocontrolreg(14 downto 12);
	alias timerenable  : std_logic  is  Autocontrolreg(15);
	signal timer : std_logic; 
	signal dtimer : std_logic; 	
	
-- channel descriptor related signals
	signal odesc: std_logic_vector(31 downto 0);
	signal adesc: std_logic_vector(31 downto 0);
	signal odescptr: std_logic_vector(3 downto 0);
	signal adescptr: std_logic_vector(3 downto 0);

component SRL16E
--
    generic (INIT : bit_vector);


--
    port (D   : in  std_logic;
          CE  : in  std_logic;
          CLK : in  std_logic;
          A0  : in  std_logic;
          A1  : in  std_logic;
          A2  : in  std_logic;
          A3  : in  std_logic;
          Q   : out std_logic); 
end component;

  component SRLC32E
--
    generic (INIT : bit_vector);


--
    port (D   : in  std_logic;
          CE  : in  std_logic;
          CLK : in  std_logic;
          A   : in  std_logic_vector(4 downto 0);
          Q   : out std_logic); 
  end component;
	 
begin 

	ofifo: for i in 0 to 35 generate
		asr32e: SRLC32E generic map (x"00000000") port map(
 	  D   => opushdata(i),
          CE  => hostpush,
          CLK => clk,
          A  => opopadd,
          Q   => opopdata(i)
			);	
  	end generate;

	ififo: for i in 0 to 31 generate
		asr32e: SRLC32E generic map (x"00000000") port map(
          D => SPISRegIn(i),
          CE => ipush,
          CLK => clk,
          A => ipopadd,
          Q => ipopdata(i)
			);	
  	end generate;

	autosendtable: for i in 0 to 35 generate
		asr32e: SRLC32E generic map (x"00000000") port map(
          D => opushdata(i),
          CE => loadasend,
          CLK => clk,
          A => autosendaddr,
          Q => autosenddata(i)
			);	
  	end generate;

	chandesc: for i in 0 to 31 generate
		asr16e: SRL16E generic map (x"0000") port map(
          D => ibus(i),
          CE => loaddesc,
          CLK => clk,
          A0 => odescptr(0),				-- from the address that was pushed
          A1 => odescptr(0),				
          A2 => odescptr(0),				
          A3 => odescptr(0),				
          Q => odesc(i)
			);	
  	end generate;	

	autochandesc: for i in 0 to 31 generate
		asr16e: SRL16E generic map (x"0000") port map(
          D   => ibus(i),
          CE  => loadautodesc,
          CLK => clk,
          A0   => adescptr(0),			-- from the address that was pushed
          A1   => adescptr(1),			
          A2   => adescptr(2),			
          A3   => adescptr(3),			
          Q   => adesc(i)
          		);
          end generate;		

	outfifo: process (clk,opopdata,odatacounter)
	begin
		if rising_edge(clk) then
			
			if hostpush = '1'  and opop = '0'  then
				if odatacounter /= 32 then	-- a push
					-- always increment the data counter if not full
					odatacounter <= odatacounter +1;
					opopadd <= opopadd +1;						-- popadd must follow data down shiftreg
				end if;	
			end if;		 		
						   
			if (opop = '1') and (hostpush = '0') and (ofifohasdata = '1') then	-- a pop
				-- always decrement the data counter if not empty
				odatacounter <= odatacounter -1;
				opopadd <= opopadd -1;
			end if;

-- if both push and pop are asserted we dont change either counter
	  
			if clear = '1' then -- a clear fifo
				opopadd  <= (others => '1');
				odatacounter <= (others => '0');
			end if;	
	
		end if; -- clk rise
		if odatacounter = 0 then
			ofifohasdata <= '0';
		else
			ofifohasdata <= '1';
		end if;
	end process outfifo;

	infifo: process (clk,ipopdata,odatacounter)
	begin
		if rising_edge(clk) then
			
			if ipush = '1'  and hostpop = '0'  then
				if idatacounter /= 32 then	-- a push
					-- always increment the data counter if not full
					idatacounter <= idatacounter +1;
					ipopadd <= ipopadd +1;						-- popadd must follow data down shiftreg
				end if;	
			end if;		 		
						   
			if (hostpop = '1') and (ipush = '0') and (ififohasdata = '1') then	-- a pop
				-- always decrement the data counter if not empty
				idatacounter <= idatacounter -1;
				ipopadd <= ipopadd -1;
			end if;

-- if both push and pop are asserted we dont change either counter
	  
			if clear = '1' then -- a clear fifo
				ipopadd  <= (others => '1');
				idatacounter <= (others => '0');
			end if;	
	
		end if; -- clk rise
		if idatacounter = 0 then
			ififohasdata <= '0';
		else
			ififohasdata <= '1';
		end if;
	end process infifo;


	aspiinterface: process (clk,  ModeReg, ClockFF, LFrame,
	                        SPISregIn,SPISregOut, BitcountReg, opopdata,
				Dav,RateDivReg,addr, ibus, CSIdle,
				hostpop, ipopdata, readcount, 
				idatacounter, odatacounter)
	begin
		if rising_edge(clk) then
			
			StartCycle(1) <= Startcycle(0);
			StartCycle(2) <= Startcycle(1);
			
			OldBitCount5 <= BitCount(5);
			OldLFrame <= LFrame;

			if autosendreq = '1' then
				if ofifohasdata = '1' then
					autosendcollision <= '1';
				else
					autosendbusy <= '1';
					autosendaddr <= "00000";
					autosendreq <= '0';
				end if;
			end if;						
		
			if autosendbusy = '0' then
				odescptr <= opopdata(35 downto 32);	-- If no auto send, descriptor address comes from odatafifo
				ModeReg <= odesc;	
			else        
				adescptr <= autosenddata(35 downto 32);	-- with autosend, descriptor address comes from autosenddata
				ModeReg <= adesc;		
			end if;
						
			if (StartCycle = "000" ) and (Run = '0')  then				
			-- if SPI shift registers are free and we have data and hold time is passed
				if (ofifohasdata = '1' and opop = '0' and autosendbusy = '0') or	-- normal (write) send
				   (ofifohasdata = '0' and autosendbusy ='1') then			-- autosend
					StartCycle(0) <= '1';						-- we need a few clocks from data available until the mode reg is valid
					CSIdle <= '0';	
				end if;
			end if;
			
			if StartCycle = "111" then			-- load all count registers and assert CS			
				StartCycle <= "000" ;
				LoadData <= '1';
				ClockFF <= CPOL;			-- load local variables from ModeReg
				RateDiv <= RateDivReg;	
				CSHoldTimer <= RateDivReg;							
				BitCount <= BitCountReg;
				CSIdleTimer <= CSIdleTimerReg;
				DontEchoReg <= DontEcho;
				CSPrescale <= 7;
				SPISregIn <= x"00000000";
				LFrame <= '1';
				EFrame <= '1';		
				Run <= '1';	
				FrameStart <= '1';
			end if;
			
			
			if Dav = '1' then 
				if DontEchoReg = '0' then
					ipush <= '1';			-- push SPI recieve data on ififo
				end if;
				Dav <= '0';
				Run <= '0';				-- we're done for this cycle except push which is overlapped
			end if;
			
			if ipush = '1' then
				ipush <= '0';
			end if;
			
				
			if loaddata = '1' then 
				loaddata <= '0';
				if autosendbusy = '1' then
					SPISregOut <= autosenddata(31 downto 0);
					autosendaddr <= autosendaddr +1;
					if autosendaddr = autosendlength then
						autosendaddr <=  "00000";
						autosendbusy <= '0';
					end if;	
				else
					SPISregOut <= opopdata(31 downto 0);
					opop <= '1';
				end if;
			end if;
			
			if opop = '1' then 
				opop <= '0';
			end if;
			
										
			if (Run = '1')  and (BitCount(5) = '0') and (CSIdle = '0') and (CSHold= '0')  then -- Dual shift register SPI							--
				if RateDiv = 0 then
					RateDiv <= RateDivReg;
					if ClockFF = '0' then						-- rising clock edge
						ClockFF <= '1';
						if CPOL = '1' then					-- When CPOL is high we stop in the high state
							BitCount <= BitCount -1;
							if ((BitCount = 8) or (Bitcount = 16) or (BitCount = 24)) and (ByteMode = '1') then
								CSHold <= '1';
								CSHoldTimer <= RateDivReg;								
							end if;	
						end if;
						if (CPOL = CPHA) then 
							SPISregIn <= SPISregIn(30 downto 0) & SPIData;	-- sample input on rising edge 								
						end if;	
						if (CPOL /= CPHA) then 
							SPISregOut <= SPISregOut(30 downto 0) & '0';	-- shift output on rising edge 								
						end if;															
 						FrameStart <= '0';					-- to mask first falling edge in CPOL = 1 mode 
 					else								-- falling clock edge
						ClockFF <= '0';
						if CPOL = '0' then					-- when CPOL is low we stop in the low state
							BitCount <= BitCount -1;
							if ((BitCount = 8) or (Bitcount = 16) or (BitCount = 24)) and (ByteMode = '1') then
								CSHold <= '1';
								CSHoldTimer <= RateDivReg;	
							end if;	
						end if;
						if (CPOL = '0') and  (CPHA = '1') then					
							SPISregIn <= SPISregIn(30 downto 0) & SPIData; 	-- shift input on falling edge
						end if;	
						if CPOL = '1' and CPHA = '0' then					
							if FrameStart = '0' then
								SPISregIn <= SPISregIn(30 downto 0) & SPIData; 	-- shift input on second falling edge if CPOL is 1
							end if;
						end if;	
						if CPOL = '0' and  CPHA = '0' then 
							SPISregOut <= SPISregOut(30 downto 0) & '0';	-- shift output on falling edge 								
						end if;															
						if CPOL = '1' and  CPHA = '1' then 
							if FrameStart = '0' then
								SPISregOut <= SPISregOut(30 downto 0) & '0';	-- shift output on second falling edge if CPOL is 1
							end if;									
						end if;															
					end if;			
				else
					RateDiv <= RateDiv -1;
				end if;							
			end if;


			if ((BitCount(5) = '1') and (OldBitCount5 = '0') and (Run = '1')) then		
				CSHold <= '1';					-- underflow so done
				CSHoldTimer <= RateDivReg;	
			end if;
						
			if (CSHold = '1') and (CSHoldTimer /= 0)	then	-- CSHold delay
				CSHoldTimer <= CSHoldTimer -1;
			end if;

			if (CSHold = '1') and (CSHoldTimer = 0)	then		-- Done with CS hold time
				CSHold <= '0';
				CSIdle <= '1';
				CSIdleTimer <= CSIdleTimerReg;						
				CSPrescale <= 7;
				LFrame <= '0';					-- Lframe cleared
				if DontClearFrame = '0' then
					EFrame <= '0';				-- EFrame only cleared if DontClearFrame is false
				end if;	
			end if;
				

			if (CSIdle ='1') and (CSIdleTimerDone = '1') and (BitCount(5) = '1') then 	-- end of cycle						
				CSIdle <= '0';
				Dav <= '1';
			end if;	


			if (CSIdle ='1') and (CSIdleTimerDone = '1') and (BitCount(5) = '0')  then	-- in the middle of a byte mode transfer 							
				CSIdle <= '0';
				Lframe <= '1';
				Eframe <= '1';
			end if;	

			if (CSIdle = '1') and (CSIdleTimerDone = '0') then
				if CSPrescale /= 0 then
					CSPrescale <= CSPrescale -1;
				else
					CSIdleTimer <= CSIdleTimer -1;
					CSPrescale <= 7;
				end if;	
			end if;	

			if loadautocontrolreg = '1' then
				autocontrolreg <= ibus(15 downto 0);
			end if;

			if clear = '1' then 
				LFrame <= '0';
				EFrame <= '0';
				Dav <= '0';
				LoadData <= '0';
				StartCycle <= "000";
				CSIdleTimerDone <= '1';
				ipush <= '0';
				CSIdle <= '0';
				Run <= '0';
				FrameStart <= '0';
				autosendaddr <= "00000";
				autosendreq <= '0';
				autosendbusy <= '0';
			end if;

			if ((timer = '1') and (dtimer = '0') and (autosendenable = '1') and (timerenable = '1')) or
			   ((autosendenable = '1') and (startautosend = '1'))  then 
				autosendreq <= '1';
			end if;	
			dtimer <= timer;
			
		end if; -- clk

		case timerselect is
			when "000" => timer <= timers(0);
			when "001" => timer <= timers(1);
			when "010" => timer <= timers(2);
			when "011" => timer <= timers(3);
			when "100" => timer <= timers(4);	
			when others => timer <= timers(0);
		end case;						
		
		
		SPIData <= spiin;

		opushdata <= addr & ibus;			--  push address to select descriptor at far end of FIFO


		obus <= (others => 'Z');
      		if hostpop =  '1' then
			obus <= ipopdata;
		end if;

		if readautocontrolreg = '1' then
			obus(4 downto 0) <= autosendlength;
			obus(7 downto 5) <= (others => '0');
			obus(8) <= autosendenable;
			obus(9) <= autosendbusy;
			obus(10) <= autosendcollision;
			obus(11) <= '0';
			obus(14 downto 12) <= TimerSelect;
			obus(15) <= timerenable;
			obus(31 downto 16) <= (others => '0');
		end if;	
				
		if readcount =  '1' then
			obus(5 downto 0) <= idatacounter;
			obus(7 downto 6)  <= (others => '0');
			obus(13 downto 8) <= odatacounter;
			obus(15 downto 14) <= (others => '0');
			obus(19 downto 16) <= adescptr;
			obus(31 downto 20) <= (others => '0');
		end if;
			
		spiclk <= ClockFF;
		
		spiframe <= not EFrame;
		
		if gatedcs then							-- gated/decoded CS/frame = DBSPI
			for i in CSwidth-1 downto 0 loop
				if i = conv_integer(CSReg) then 
					spicsout(i) <= not EFrame;
				else
					spicsout(i) <= '1';
				end if;	
			end loop;  
			report("Decoded BSPI found");
		else
			spicsout <= CSReg;					-- decoded select with separate frame = BSPI
			report("Normal BSPI found");
		end if;
		spiout <= SPISRegOut(conv_integer(BitCountReg(4 downto 0)));
--		spiout <= DontEchoReg;						-- debug
	end process aspiinterface;

end Behavioral;
