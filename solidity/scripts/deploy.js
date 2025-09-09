const fs = require("fs");
const path = require("path");

async function main() {
  const MessageRegistry = await ethers.getContractFactory("MessageRegistry");
  const registry = await MessageRegistry.deploy();
  if (typeof registry.waitForDeployment === "function") {
    await registry.waitForDeployment();
  } else if (typeof registry.deployed === "function") {
    await registry.deployed();
  } else {
    await new Promise(res => setTimeout(res, 1000));
  }

  const deployedAddress = registry.address ?? registry.target;
  console.log("MessageRegistry deployed to:", deployedAddress);

  const artifact = await hre.artifacts.readArtifact("MessageRegistry");

  const out = {
    address: deployedAddress,
    abi: artifact.abi
  };

  // write to project-root python folder
  const outPath = path.join(__dirname, '..', 'python', 'contract_info.json');
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
  console.log('Wrote contract info to', outPath);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
