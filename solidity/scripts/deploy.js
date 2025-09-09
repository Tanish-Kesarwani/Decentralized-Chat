const fs = require('fs');
const path = require('path');

async function main() {
  const MessageRegistry = await ethers.getContractFactory("MessageRegistry");
  const registry = await MessageRegistry.deploy();

  // ethers v5 used deployed(), ethers v6 uses waitForDeployment()
  if (typeof registry.deployed === 'function') {
    await registry.deployed();
  } else if (typeof registry.waitForDeployment === 'function') {
    await registry.waitForDeployment();
  } else {
    // tiny fallback
    await new Promise(res => setTimeout(res, 1000));
  }

  // registry.address (v5) or registry.target (v6)
  const deployedAddress = registry.address ?? registry.target;
  console.log("MessageRegistry deployed to:", deployedAddress);

  // read compiled artifact to grab ABI
  const artifact = await hre.artifacts.readArtifact("MessageRegistry");

  // write contract address + ABI to python/contract_info.json
  const out = {
    address: deployedAddress,
    abi: artifact.abi
  };
  const outPath = path.join(__dirname, '..', '..', 'python', 'contract_info.json');
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
  console.log('Wrote contract info to', outPath);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
