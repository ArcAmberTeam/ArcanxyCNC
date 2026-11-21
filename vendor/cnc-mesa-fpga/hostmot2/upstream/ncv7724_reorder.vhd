--
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

-- Basically reorder the output data into SPI bit order, taking into account 
-- the pin renaming for a sane PCB layout. Do the same for the return status bits

-- Bit to PCB renumber:

-- BIT     NCV7724 pin name (1..8)	status bits	in status bytes	
-- 0       1 								0-1,2			0-1,0-2	
-- 1       5 								0-9,10		1-1,1-2	
-- 2       7 								1-1,2			2-1,2-2
-- 3       6 								0-11,12		1-3,1-4
-- 4       4 								0-7,8			0-7,1-0
-- 5       3 								0-5,6			0-5,0-6
-- 6       8 								1-3,4			2-3,2-4
-- 7       2 								0-3,4			0-3,0-4

entity ncv7724_reorder is
    Port ( clk : in  std_logic;
           ibus : in  std_logic_vector (7 downto 0);
           obus : out  std_logic_vector (7 downto 0);
			  loadena : in std_logic;
			  loadconfig : in std_logic;
           loadstatus0 : in std_logic;
           loadstatus1 : in std_logic;
           loadstatus2 : in std_logic;
           loadstatus3 : in std_logic;
			  readoutdata0 : in std_logic;		-- SPI output data byte 0 HBEN= 0
           readoutdata1 : in std_logic;		-- SPI output data byte 1
			  readoutdata2 : in std_logic;		-- SPI output data byte 2 HBEN= 1
           readoutdata3 : in std_logic;		-- SPI output data byte 3
           readoutstatus0 : in std_logic;		-- all status 0 bits
           readoutstatus1 : in std_logic;		-- all status 1 bits
			  readhbridgestatus : in std_logic
			  );
			  
end ncv7724_reorder;

architecture Behavioral of ncv7724_reorder is

-- first the write registers for outgoing data
signal enareg: std_logic_vector (7 downto 0);
signal configreg: std_logic_vector (7 downto 0);
-- then the write registers for incoming data
signal statusreg0: std_logic_vector (7 downto 0);
signal statusreg1: std_logic_vector (7 downto 0);
signal statusreg2: std_logic_vector (7 downto 0);
signal statusreg3: std_logic_vector (7 downto 0);


begin


	ancv7724_reorder: process (clk,loadena,loadconfig,loadstatus0,loadstatus1,
				loadstatus2,readoutdata0,readoutdata1,readoutdata3, 
				readoutstatus0,readoutstatus1,readhbridgestatus)
	begin
		if rising_edge(clk) then
			if loadena= '1' then 
				enareg <= ibus;
			end if;	
			if loadconfig= '1' then 
				configreg <= ibus;
			end if;	
			if loadstatus0= '1' then 
				statusreg0 <= ibus;
			end if;	
			if loadstatus1= '1' then 
				statusreg1 <= ibus;
			end if;	
			if loadstatus2= '1' then 
				statusreg2 <= ibus;
			end if;	
			if loadstatus3= '1' then 
				statusreg3 <= ibus;
			end if;	
		end if; -- clk

		obus <= (others => 'Z');
		if readoutdata0 = '1' then		-- LSB of first command
			obus(0) <= '1'; 				-- OVLO
			obus(1) <= configreg(0); 	--	remapped output bits and 1 enable
			obus(2) <= configreg(7); 	
			obus(3) <= configreg(5); 
			obus(4) <= configreg(4); 
			obus(5) <= configreg(1);
			obus(6) <= configreg(3); 
			obus(7) <= enareg(0); 			
		end if;

		if readoutdata1 = '1' then		-- MSB of first command
			obus(0) <= enareg(7); 		-- OVLO
			obus(1) <= enareg(5); 		--	remapped enable bits			
			obus(2) <= enareg(4); 	
			obus(3) <= enareg(1); 
			obus(4) <= enareg(3); 
			obus(5) <= '0';				-- ULDSC
			obus(6) <= '0'; 				-- HBSEL (0 on first word)
			obus(7) <= '0';				-- SRR 			
		end if;

		if readoutdata2 = '1' then		-- LSB of second command
			obus(0) <= '1'; 				-- OVLO
			obus(1) <= configreg(2); 	--	remapped output bits and 1 enable
			obus(2) <= configreg(6); 	
			obus(3) <= '0'; 				-- 4 unused bits
			obus(4) <= '0'; 
			obus(5) <= '0';
			obus(6) <= '0'; 
			obus(7) <= enareg(2); 			
		end if;

		if readoutdata3 = '1' then		-- LSB of second command
			obus(0) <= enareg(6); 		
			obus(1) <= '0'; 				-- 4 unused bits
			obus(2) <= '0'; 	
			obus(3) <= '0'; 
			obus(4) <= '0';
			obus(5) <= '0';				-- ULDSC
			obus(6) <= '1'; 				-- HBSEL (1 on second word)
			obus(7) <= '0';				-- SRR 			
		end if;

		if readoutstatus0 = '1' then		-- output status bit 0 of all 8 outputs
			obus(0) <= statusreg0(1); 		
			obus(1) <= statusreg1(1); 				
			obus(2) <= statusreg2(1); 	
			obus(3) <= statusreg1(3); 
			obus(4) <= statusreg0(7);
			obus(5) <= statusreg0(5);				
			obus(6) <= statusreg2(3); 				
			obus(7) <= statusreg0(3);							
		end if;

		if readoutstatus1 = '1' then		-- output status bit 1 of all 8 outputs
			obus(0) <= statusreg0(2); 		
			obus(1) <= statusreg1(2); 				
			obus(2) <= statusreg2(2); 	
			obus(3) <= statusreg1(4); 
			obus(4) <= statusreg1(0);
			obus(5) <= statusreg0(6);				
			obus(6) <= statusreg2(4); 				
			obus(7) <= statusreg0(4);							
		end if;

		if readhbridgestatus = '1' then		-- bridge status 		
			obus(0) <= '0';				
			obus(1) <= '0';				
			obus(2) <= statusreg0(0) or statusreg2(0);	-- TW  bits 2 and 3 to match SS OT and OC
			obus(3) <= statusreg1(7) or statusreg3(7); 	-- OCS		
			obus(4) <= statusreg1(6) or statusreg3(6);	-- PSF
			obus(5) <= statusreg1(5) or statusreg3(5);	-- ULD
			obus(6) <= '0';				
			obus(7) <= '0';				
		end if;
		
	end process;	


end Behavioral;

